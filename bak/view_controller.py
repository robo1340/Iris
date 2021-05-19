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

sys.path.insert(0,'..') #need to insert parent path to import something from message

#import notification.AndroidNotification as notification
from androidtoast import toast
from plyer import vibrator

new_gps_contact_vibe_pattern = (0,0.5)
text_msg_vibe_pattern = (0,1)
ack_vibe_pattern = (0,0.25,0.15,0.25,0.15,0.25)
gps_beacon_contact_vibe_pattern = (0, 0.25)

from messages import *
import common

from kivy.logger import Logger as log
from kivy.clock import Clock

def exception_suppressor(func):
    def meta_function(*args, **kwargs):
        try:
            func(*args,**kwargs)
        except BaseException:
            pass
    return meta_function

class ViewController():

    def __init__(self):
        self.tx_time = time.time()
        self.gps_tx_time = time.time()
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:8001")
    
        self.ui = None
        
        self.client = SimpleUDPClient('127.0.0.2',8000) #create the UDP client
    
        self.contacts_dict = {} #a dictionary describing the current gps contacts that have been placed
            #keys are the callsign string, values are a GPSMessaageObject
    
        #create the UDP server and map callbacks to it
        dispatcher = Dispatcher()
        dispatcher.map('/test',self.test_handler)
        dispatcher.map("/txt_msg_rx", self.txt_msg_handler)
        dispatcher.map("/gps_msg", self.gps_msg_handler)
        dispatcher.map('/my_gps_msg', self.my_gps_msg_handler)
        dispatcher.map('/ack_msg', self.ack_msg_handler)
        dispatcher.map('/status_indicator', self.transceiver_status_handler)
        dispatcher.map('/tx_success', self.tx_success_handler)
        dispatcher.map('/tx_failure', self.tx_failure_handler)
        dispatcher.map('/rx_success', self.rx_success_handler)
        dispatcher.map('/rx_failure', self.rx_failure_handler)
        dispatcher.map('/gps_lock_achieved', self.gps_lock_achieved_hander)
        dispatcher.map('/signal_strength',self.signal_strength_handler)
        dispatcher.map('/retry_msg',self.retry_msg_handler)
        dispatcher.map('/header_info', self.header_info_handler)
        
        #self.server = BlockingOSCUDPServer(('127.0.0.1', 8000), dispatcher)
        self.server = ThreadingOSCUDPServer(('127.0.0.1', 8000), dispatcher)
    
        self.view_controller_func = lambda server : server.serve_forever() #the thread function
    
        #self.thread = common.StoppableThread(target = self.view_controller_func, args=(self.server,))
        self.thread = common.StoppableThread(target = self.zmq_func, args=(self.socket,))
        self.thread.start()
        
        self.stop = lambda : self.server.shutdown()
    
    #the thread function
    #def view_controller_func(server):
    #    #while(True):
    #    server.serve_forever()
    def zmq_func(self,socket):
        message = socket.recv()
        log.info("========================================================Received zmq message: %s" % message)
    
    ###############################################################################
    ############### Methods for sending messages to the Service ###################
    ###############################################################################
    
    ## @brief send a text message to the service to be transmitted
    #
    def send_txt_message(self, txt_msg):
        log.debug('sending a text message to the service')
        #log.info(txt_msg.carrier_len)
        self.client.send_message('/txt_msg_tx', txt_msg.marshal())
    
    ## @brief send a new callsign entered by the user to the service
    #
    def send_my_callsign(self, my_callsign):
        self.client.send_message('/my_callsign',my_callsign)
    
    ##@brief send the service a new gps beacon state and gps beacon period
    ##@param gps_beacon_enable True if the gps beacon should be enabled, False otherwise
    ##@param gps_beacon_period, the period of the gps beacon (in seconds)
    #
    def send_gps_beacon_command(self, gps_beacon_enable, gps_beacon_period):
        log.debug('sending a gps beacon command to the Service')
        self.client.send_message('/gps_beacon',(gps_beacon_enable, gps_beacon_period))
        
    ##@brief send the service a command to transmit one gps beacon immeadiatly
    #
    def gps_one_shot_command(self):
        log.debug('sending a gps one shot command to the service')
        self.client.send_message('/gps_one_shot',(True,))
        
    ##@brief send the service a command to shutdown
    def service_stop_command(self):
        log.debug('view controller shutting down the service')
        self.client.send_message('/stop',(True,))
    
    ###############################################################################
    ## Handlers for when the View Controller receives a message from the Service ##
    ###############################################################################
    
    ##@brief handler for when a TextMessage object is received from the service
    ##@param args, a list of values holding the TextMessage's contents
    #
    def txt_msg_handler(self, address, *args):
        log.info('received text message from the service')
        msg = MessageObject.unmarshal(args[0])
        if (msg is not None):
            if (msg.header.src_callsign == self.ui.my_callsign): #this is my own message
                return
            
            Clock.schedule_once(functools.partial(self.ui.addMessageToUI, msg, False), 0)
            
            gps_msg = msg.get_dummy_beacon()
            if not msg.header.src_callsign in self.contacts_dict:
                Clock.schedule_once(functools.partial(self.ui.addNewGPSContactToUI, gps_msg), 0)
            else:
                Clock.schedule_once(functools.partial(self.ui.updateGPSContact, gps_msg), 0)
            self.contacts_dict[msg.header.src_callsign] = gps_msg
            
            toast('Text from ' + msg.header.src_callsign)
            vibrator.pattern(pattern=text_msg_vibe_pattern)
        
    
    ##@brief handler for when a GPSMessage object is received from the service that was received by the radio
    ##@param args, a list of values holding the GPSMessage's contents
    #
    def gps_msg_handler(self, address, *args):
        gps_msg = GPSMessageObject.unmarshal(args[0])
        if (gps_msg is not None):
            if (gps_msg.src_callsign == self.ui.my_callsign): #return immeadiatly, this is my own beacon
                return
            
            if not gps_msg.src_callsign in self.contacts_dict:
                vibrator.pattern(pattern=new_gps_contact_vibe_pattern)
                Clock.schedule_once(functools.partial(self.ui.addNewGPSContactToUI, gps_msg), 0)
            else:
                Clock.schedule_once(functools.partial(self.ui.updateGPSContact, gps_msg), 0)
                vibrator.pattern(pattern=gps_beacon_contact_vibe_pattern)
            self.contacts_dict[gps_msg.src_callsign] = gps_msg
            toast('GPS Beacon from ' + gps_msg.src_callsign)
            
            log.debug('received gps message from the service: ' + gps_msg.src_callsign)
            #Clock.schedule_once(functools.partial(self.ui.addGPSMessageToUI, gps_msg), 0)
    
    ##@brief handler for when a GPSMessage object is received from the service this is my current location
    ##@param args, a list of values holding the GPSMessage's contents
    #
    def my_gps_msg_handler(self, address, *args):
        gps_msg = GPSMessageObject.unmarshal(args[0])
        if (gps_msg is not None):
            Clock.schedule_once(functools.partial(self.ui.update_my_displayed_location, gps_msg.location), 0)

    
    def ack_msg_handler(self, address, *args):
        log.debug('received an acknoweledgement message from the service: '+ str(args))
        if (args[1] == self.ui.my_callsign): #this is my ack
            return
        
        Clock.schedule_once(functools.partial(self.ui.addAckToUI, (int(args[0])) ), 0)  
        toast('Ack received from ' + args[1])
        vibrator.pattern(pattern=ack_vibe_pattern)
    
    #
    def transceiver_status_handler(self, address, *args):
        #log.info('received a status update from the service')
        Clock.schedule_once(functools.partial(self.ui.updateStatusIndicator, args[0]), 0)
        
    #
    def tx_success_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_tx_success_cnt, args[0]), 0)
        
    #
    def tx_failure_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_tx_failure_cnt, args[0]), 0)
    
    #
    def rx_success_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_rx_success_cnt, args[0]), 0)
    
    #
    def rx_failure_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_rx_failure_cnt, args[0]), 0)
        
    #
    def gps_lock_achieved_hander(self, address, *args):
        log.info('gps lock achieved set to- ' + str(args[0]))
        Clock.schedule_once(functools.partial(self.ui.notifyGPSLockAchieved), 0) #update the ui elements to show gps lock achieved
        
    #
    def signal_strength_handler(self, address, *args):
        #log.info('view controller received signal strength- ' + str(args[0]))
        Clock.schedule_once(functools.partial(self.ui.update_signal_strength, args[0]), 0)
    
    def retry_msg_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.updateRetryCount, int(args[0]), int(args[1]) ), 0) 
        log.info('received a retry message from the service controller')
        #Clock.schedule_once(functools.partial(self.ui.updateRetryCount, int(args[0]), int(args[1]) ), 0) 
        
    def header_info_handler(self, address, *args):
        header_info = AckSequenceList.unmarshal(args[0])
        Clock.schedule_once(functools.partial(self.ui.updateStatusIndicator, header_info), 0)
        
    def test_handler(self, address, *args):
        log.info(args)
