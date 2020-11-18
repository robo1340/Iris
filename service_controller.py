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
from datetime import datetime

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject, GPSMessageObject
import common

log = logging.getLogger('__name__')

def exception_suppressor(func):
    def meta_function(*args, **kwargs):
        try:
            func(*args,**kwargs)
        except BaseException:
            pass
    return meta_function

class ServiceController():

    def __init__(self, il2p, ini_config, gps=None, osm=None):
        print('service controller constructor')
        self.il2p = il2p
        self.gps = gps
        self.osm = osm
        
        self.gps_beacon_enable = True if (ini_config['MAIN']['gps_beacon_enable'] == '1') else False
        period_str = ini_config['MAIN']['gps_beacon_period']
        self.gps_beacon_period = int(period_str) if period_str.isdigit() else 30
        
        self.gps_beacon_sched = sched.scheduler(time.time, time.sleep)
        
        self.client = SimpleUDPClient('127.0.0.1',8000) #create the UDP client
        
        #create the UDP server and map callbacks to it
        dispatcher = Dispatcher()
        dispatcher.map("/txt_msg_tx", self.txt_msg_handler)
        dispatcher.map("/my_callsign", self.my_callsign_handler)
        dispatcher.map("/gps_beacon", self.gps_beacon_handler)
        dispatcher.map('/gps_one_shot',self.gps_one_shot_handler)
        #dispatcher.set_default_handler(default_handler)
        self.server = ThreadingOSCUDPServer(("127.0.0.2", 8000), dispatcher)
    
        self.thread = common.StoppableThread(target = self.service_controller_func, args=(self.server,))
        self.thread.start()

        #setup some lambda functions
        #self.stop = lambda : self.thread.stop()
        
    ###############################################################################
    ## Handlers for when the service receives a message from the View Controller ##
    ###############################################################################
    
    ## @brief callback for when the View Controller sends a UDP datagram containing a text message to be transmitted
    @exception_suppressor
    def txt_msg_handler(self, address, *args):
        print('text message received from the View Controller')
        txt_msg = TextMessageObject.unmarshal(args)
        self.il2p.msg_send_queue.put(txt_msg)
    
    ## @brief callback for when the View Controller sends a new callsign
    @exception_suppressor
    def my_callsign_handler(self, address, *args):
        print('my callsign received from View Controller')
        self.il2p.setMyCallsign(args[0])
    
    @exception_suppressor
    def gps_beacon_handler(self, address, *args):
        print('gps beacon settings received from View Controller')
        self.gps_beacon_enable = args[0]
        self.gps_beacon_period = args[1]
        if (self.gps_beacon_enable == True):
            self.schedule_gps_beacon()
        else: #logic to cancel the beacon if self.gps_beacon_enable is False
            for event in self.gps_beacon_sched.queue:
                self.gps_beacon_sched.cancel(event)
    
    @exception_suppressor
    def gps_one_shot_handler(self,address, *args):
        print('gps one shot command received from View Controller')
        self.transmit_gps_beacon()
    
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
    
    @exception_suppressor
    def send_txt_message(self, txt_msg):
        print('sending text message to the View Controller')
        #print(txt_msg.getInfoString())
        #print(txt_msg.marshal())
        self.client.send_message('/txt_msg_rx', txt_msg.marshal())
    
    #@exception_suppressor
    def send_gps_message(self, gps_msg):
        print('sending gps message to View Controller')
        
        self.client.send_message('/gps_msg', gps_msg.marshal()) #send the GPS message to the UI so it can be displayed
        
        if ((self.osm is not None) and (gps_msg.src_callsign != self.il2p.my_callsign)):
            self.osm.placeContact(gps_msg.lat(), gps_msg.lon(), gps_msg.src_callsign, datetime.now().strftime("%H:%M:%S")+'\n'+gps_msg.getInfoString())
    
    ##@brief send the View Controller my current gps location contained in a GPSMessage object
    ##@param gps_msg a GPSMessage object
    def send_my_gps_message(self, gps_msg):
        print('sending my gps message to View Controller')
        self.client.send_message('/my_gps_msg', gps_msg.marshal())
    
    @exception_suppressor
    def send_ack_message(self, ack_key):
        print('sending message acknowledgment to View Controller')
        self.client.send_message('/ack_msg', ( str(ack_key[0]), str(ack_key[1]), str(ack_key[2]) ) )
    
    @exception_suppressor
    def send_status(self, status):
        #print('service sending status to View Controller')
        self.client.send_message('/status_indicator', status)
    
    @exception_suppressor
    def send_statistic(self, type, value):
        self.client.send_message('/' + type, value)
    
    @exception_suppressor
    def send_test(self):
        self.client.send_message('/test', ['hhfg', 'BAYWAX', 'WAYWAX', 1, 0])
    
    ###############################################################################
    ############### Methods for controlling the il2p link layer ###################
    ###############################################################################
    
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
            gps_msg = GPSMessageObject(loc, self.il2p.my_callsign)
            self.send_my_gps_message(gps_msg) #send my gps location to the View Controller so it can be displayed
            
            self.il2p.msg_send_queue.put(gps_msg) #send my gps location to the il2p transceiver so that it can be transmitted

    ###############################################################################
    ############################ Thread Routines ##################################
    ###############################################################################

    def service_controller_func(self, server):
        log.info('service server started')
        #self.send_test()

        server.serve_forever()  # Blocks forever
        
        print('ERROR: service controller thread died')

