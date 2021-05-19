import threading
import time
import random
import logging
import queue
import random
import time
import sched
import sys
import functools
import zmq
from datetime import datetime

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import *
import common
import IL2P_API
from IL2P import IL2P_Frame_Header

from kivy.logger import Logger as log

def exception_suppressor(func):
    def meta_function(*args, **kwargs):
        try:
            func(*args,**kwargs)
        except BaseException:
            pass
    return meta_function

class ServiceController():

    def __init__(self, il2p, ini_config, gps=None, osm=None):
        log.info('service controller constructor')
        self.il2p = il2p
        self.gps = gps
        self.osm = osm
        self.isStopped = False
        if (self.gps != None):
            self.gps.start(self)
        
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://127.0.0.1:8001")
        socket.send(b"Hello pyzmq")
        
        self.gps_beacon_enable = True if (ini_config['MAIN']['gps_beacon_enable'] == '1') else False
        period_str = ini_config['MAIN']['gps_beacon_period']
        self.gps_beacon_period = int(period_str) if period_str.isdigit() else 30
        
        self.gps_beacon_sched = sched.scheduler(time.time, time.sleep)
        self.carrier_length = int(ini_config['MAIN']['carrier_length'])
        
        self.client = SimpleUDPClient('127.0.0.3',8000) #create the UDP client
        
        #create the UDP server and map callbacks to it
        dispatcher = Dispatcher()
        dispatcher.map("/txt_msg_tx", self.txt_msg_handler)
        dispatcher.map("/my_callsign", self.my_callsign_handler)
        dispatcher.map("/gps_beacon", self.gps_beacon_handler)
        dispatcher.map('/gps_one_shot',self.gps_one_shot_handler)
        dispatcher.map('/stop',self.stop_handler)
        #dispatcher.set_default_handler(default_handler)
        self.server = ThreadingOSCUDPServer(("127.0.0.2", 8000), dispatcher)
        #self.server = BlockingOSCUDPServer(('127.0.0.2', 8000), dispatcher)

        self.service_controller_func = lambda server : server.serve_forever() #the thread function
    
        self.thread = common.StoppableThread(target = self.service_controller_func, args=(self.server,))
        self.thread.start()
        
    ###############################################################################
    ## Handlers for when the service receives a message from the View Controller ##
    ###############################################################################
    
    ## @brief callback for when the View Controller sends a UDP datagram containing a text message to be transmitted
    #@
    def txt_msg_handler(self, address, *args):
        log.info('text message received from the View Controller')
        txt_msg = MessageObject.unmarshal(args[0])
        #log.info(txt_msg.carrier_len)
        self.il2p.msg_send_queue.put((10, txt_msg))
    
    ## @brief callback for when the View Controller sends a new callsign
    
    def my_callsign_handler(self, address, *args):
        log.info('my callsign received from View Controller')
        self.il2p.setMyCallsign(args[0])
    
    #
    def gps_beacon_handler(self, address, *args):
        log.info('gps beacon settings received from View Controller')
        self.gps_beacon_enable = args[0]
        self.gps_beacon_period = args[1]
        if (self.gps_beacon_enable == True):
            self.schedule_gps_beacon()
        else: #logic to cancel the beacon if self.gps_beacon_enable is False
            for event in self.gps_beacon_sched.queue:
                self.gps_beacon_sched.cancel(event)
    
    
    def gps_one_shot_handler(self,address, *args):
        log.info('gps one shot command received from View Controller')
        self.transmit_gps_beacon()
        
    
    def stop_handler(self, address, *args):
        log.info('stopping the service threads')
        self.isStopped = True
        self.server.shutdown()
    
    ###############################################################################
    ## Handlers for when the service receives a GPS Message from the Transceiver ##
    ###############################################################################
    
    #callback for when the Transceiver receives a GPS Message
    #def gps_msg_handler(address, *args):
    #    gps_msg = GPSMessageObject.unmarshal(args)
    #    self.il2p.msg_send_queue.put(gps_msg)
    
    ###############################################################################
    ########## Methods for sending messages to the View Controller ################
    ###############################################################################
    
    
    def send_txt_message(self, msg):
        log.info('sending text message to the View Controller')
        msg.mark_time()
        self.client.send_message('/txt_msg_rx', msg.marshal())
    
    
    def send_gps_message(self, msg):
        log.debug('sending gps message to View Controller')
        gps_msg = msg.get_location()
        if (gps_msg is None):
            log.warning('a non-gps message ended up in a gps message handler')
        else:
            gps_msg.mark_time() #record the current time into the gps message
            self.client.send_message('/gps_msg', gps_msg.marshal()) #send the GPS message to the UI so it can be displayed

            if ((self.osm is not None) and (gps_msg.src_callsign != self.il2p.my_callsign)):
                self.osm.placeContact(gps_msg.lat(), gps_msg.lon(), gps_msg.src_callsign, gps_msg.time_str+'\n'+gps_msg.getInfoString())
    
    def send_header_info(self, info):
        log.info('updating header info')
        self.client.send_message('/header_info', info.marshal())
    
    ##@brief send the View Controller my current gps location contained in a GPSMessage object
    ##@param gps_msg a GPSMessage object
    def send_my_gps_message(self, gps_msg):
        log.debug('sending my gps message to View Controller')
        self.client.send_message('/my_gps_msg', gps_msg.marshal())
    
    
    def send_ack_message(self, ack_key):
        log.debug('sending message acknowledgment to View Controller')
        self.client.send_message('/ack_msg', (str(ack_key)) )
    
    
    def send_status(self, status):
        #log.info('service sending status to View Controller')
        self.client.send_message('/status_indicator', status)
    
    
    def send_statistic(self, type, value):
        self.client.send_message('/' + type, value)
    
    
    def send_test(self):
        self.client.send_message('/test', ['hhfg', 'BAYWAX', 'WAYWAX', 1, 0])
        
    
    def send_gps_lock_achieved(self, isLockAchieved):
        self.client.send_message('/gps_lock_achieved', isLockAchieved)
        
    
    def send_signal_strength(self, signal_strength):
        self.client.send_message('/signal_strength',signal_strength)
    
    
    def send_retry_message(self, ack_key, remaining_retries):
        log.info('sending retry message to View Controller')
        self.client.send_message('/retry_msg', ( str(ack_key), str(remaining_retries) ) )
    
    ###############################################################################
    ############### Methods for controlling the il2p link layer ###################
    ###############################################################################
    
    def stopped(self):
        return self.isStopped
    
    def schedule_gps_beacon(self):
        T = self.gps_beacon_period
        self.gps_beacon_sched.enter(T + 0.25*random.uniform(-T,T), 1, self.meta_transmit_gps_beacon, ())
        self.gps_beacon_sched.run()
        
    def meta_transmit_gps_beacon(self):
        self.transmit_gps_beacon()
        if (self.gps_beacon_enable):
            self.schedule_gps_beacon()
    
    def transmit_gps_beacon(self):
        if (self.gps is None):
            log.warning('WARNING: No GPS hardware detected')
            return
        else:
            loc = self.gps.getLocation()
            if (loc is None):
                log.warning('WARNING: No GPS location provided')
                return

            loc_str = str(loc).replace('\'','\"')
            gps_hdr = IL2P_Frame_Header(src_callsign=self.il2p.my_callsign, dst_callsign='', \
                                       hops_remaining=0, hops=0, is_text_msg=False, is_beacon=True, \
                                       stat1=False, stat2=False, \
                                       acks=self.il2p.forward_acks.getAcksBool(), \
                                       request_ack=False, request_double_ack=False, \
                                       payload_size=len(loc_str), \
                                       data=self.il2pforward_acks.getAcksData())
            
            gps_msg = MessageObject(header=gps_hdr, payload_str=loc_str)
            
            self.send_my_gps_message(GPSMessageObject(src_callsign=self.il2p.my_callsign, location=loc)) #send my gps location to the View Controller so it can be displayed
            
            self.il2p.msg_send_queue.put((15, gps_msg)) #send my gps location to the il2p transceiver so that it can be transmitted
       

