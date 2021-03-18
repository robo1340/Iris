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
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject, GPSMessageObject
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
        
        #self.server = BlockingOSCUDPServer(('127.0.0.1', 8000), dispatcher)
        self.server = ThreadingOSCUDPServer(('127.0.0.1', 8000), dispatcher)
    
        self.view_controller_func = lambda server : server.serve_forever() #the thread function
    
        self.thread = common.StoppableThread(target = self.view_controller_func, args=(self.server,))
        self.thread.start()
        
        self.stop = lambda : self.server.shutdown()
    
    ###############################################################################
    ############### Methods for sending messages to the Service ###################
    ###############################################################################
    
    ## @brief send a text message to the service to be transmitted
    #@exception_suppressor
    def send_txt_message(self, txt_msg):
        log.info('sending a text message to the service')
        #log.info(txt_msg.carrier_len)
        self.client.send_message('/txt_msg_tx', txt_msg.marshal())
    
    ## @brief send a new callsign entered by the user to the service
    #@exception_suppressor
    def send_my_callsign(self, my_callsign):
        self.client.send_message('/my_callsign',my_callsign)
    
    ##@brief send the service a new gps beacon state and gps beacon period
    ##@param gps_beacon_enable True if the gps beacon should be enabled, False otherwise
    ##@param gps_beacon_period, the period of the gps beacon (in seconds)
    #@exception_suppressor
    def send_gps_beacon_command(self, gps_beacon_enable, gps_beacon_period):
        log.info('sending a gps beacon command to the Service')
        self.client.send_message('/gps_beacon',(gps_beacon_enable, gps_beacon_period))
        
    ##@brief send the service a command to transmit one gps beacon immeadiatly
    #@exception_suppressor
    def gps_one_shot_command(self):
        log.info('sending a gps one shot command to the service')
        self.client.send_message('/gps_one_shot',(True,))
        
    ##@brief send the service a command to shutdown
    def service_stop_command(self):
        log.info('view controller shutting down the service')
        self.client.send_message('/stop',(True,))
    
    ###############################################################################
    ## Handlers for when the View Controller receives a message from the Service ##
    ###############################################################################
    
    ##@brief handler for when a TextMessage object is received from the service
    ##@param args, a list of values holding the TextMessage's contents
    #@exception_suppressor
    def txt_msg_handler(self, address, *args):
        log.info('received text message from the service')
        txt_msg = TextMessageObject.unmarshal(args)
        if (txt_msg is not None):
            Clock.schedule_once(functools.partial(self.ui.addMessageToUI, txt_msg, False), 0)
            if not txt_msg.src_callsign in self.contacts_dict:
                Clock.schedule_once(functools.partial(self.ui.addNewGPSContactToUI, txt_msg), 0)
            else:
                Clock.schedule_once(functools.partial(self.ui.updateGPSContact, txt_msg), 0)
            self.contacts_dict[txt_msg.src_callsign] = txt_msg
        
    
    ##@brief handler for when a GPSMessage object is received from the service that was received by the radio
    ##@param args, a list of values holding the GPSMessage's contents
    #@exception_suppressor
    def gps_msg_handler(self, address, *args):
        gps_msg = GPSMessageObject.unmarshal(args)
        if (gps_msg is not None):
            if not gps_msg.src_callsign in self.contacts_dict:
                Clock.schedule_once(functools.partial(self.ui.addNewGPSContactToUI, gps_msg), 0)
            else:
                Clock.schedule_once(functools.partial(self.ui.updateGPSContact, gps_msg), 0)
            self.contacts_dict[gps_msg.src_callsign] = gps_msg
            
            
            log.info('received gps message from the service: ' + gps_msg.src_callsign)
            #Clock.schedule_once(functools.partial(self.ui.addGPSMessageToUI, gps_msg), 0)
    
    ##@brief handler for when a GPSMessage object is received from the service this is my current location
    ##@param args, a list of values holding the GPSMessage's contents
    #@exception_suppressor
    def my_gps_msg_handler(self, address, *args):
        gps_msg = GPSMessageObject.unmarshal(args)
        if (gps_msg is not None):
            Clock.schedule_once(functools.partial(self.ui.update_my_displayed_location, gps_msg.location), 0)

    #@exception_suppressor
    def ack_msg_handler(self, address, *args):
        log.info('received an acknoweledgement message from the service: '+ str(args))
        Clock.schedule_once(functools.partial(self.ui.addAckToUI, (args[0],args[1],int(args[2])) ), 0)   
    
    #@exception_suppressor
    def transceiver_status_handler(self, address, *args):
        #log.info('received a status update from the service')
        Clock.schedule_once(functools.partial(self.ui.updateStatusIndicator, args[0]), 0)
        
    #@exception_suppressor
    def tx_success_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_tx_success_cnt, args[0]), 0)
        
    #@exception_suppressor
    def tx_failure_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_tx_failure_cnt, args[0]), 0)
    
    #@exception_suppressor
    def rx_success_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_rx_success_cnt, args[0]), 0)
    
    #@exception_suppressor
    def rx_failure_handler(self, address, *args):
        Clock.schedule_once(functools.partial(self.ui.update_rx_failure_cnt, args[0]), 0)
        
    #@exception_suppressor
    def gps_lock_achieved_hander(self, address, *args):
        log.info('gps lock achieved set to- ' + str(args[0]))
        Clock.schedule_once(functools.partial(self.ui.notifyGPSLockAchieved), 0) #update the ui elements to show gps lock achieved
        
    #@exception_suppressor
    def signal_strength_handler(self, address, *args):
        #log.info('view controller received signal strength- ' + str(args[0]))
        Clock.schedule_once(functools.partial(self.ui.update_signal_strength, args[0]), 0)
    
    def retry_msg_handler(self, address, *args):
        log.debug('received a retry message from the service controller')
        Clock.schedule_once(functools.partial(self.ui.updateRetryCount, (args[0],args[1],int(args[2])), int(args[3]) ), 0) 
        
    def test_handler(self, address, *args):
        log.info(args)