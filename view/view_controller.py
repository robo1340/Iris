import threading
import time
import random
import logging
import queue
import random
import time
import sched
import sys
from datetime import datetime

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject, GPSMessageObject
import common

log = logging.getLogger('__name__')

class ViewController():

    def __init__(self):#, ui):
        self.tx_time = time.time()
        self.gps_tx_time = time.time()
    
        #self.ui = ui
        self.ui = None
        
        self.client = SimpleUDPClient('127.0.0.2',8000) #create the UDP client
    
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
        self.server = BlockingOSCUDPServer(('127.0.0.1', 8000), dispatcher)
    
        self.thread = common.StoppableThread(target = self.view_controller_func, args=(self.server,))
        self.thread.start()
        
        #setup some lambda functions
        self.stop = lambda : self.thread.stop()
    
    ###############################################################################
    ############### Methods for sending messages to the Service ###################
    ###############################################################################
    
    #send a text message to the service to be transmitted
    def send_txt_message(self, txt_msg):
        print('sending a text message to the service')
        self.client.send_message('/txt_msg_tx', txt_msg.marshal())
    
    #send a new callsign entered by the user to the service
    def send_my_callsign(self, my_callsign):
        self.client.send_message('/my_callsign',my_callsign)
    
    ##@brief send the service a new gps beacon state and gps beacon period
    ##@param gps_beacon_enable True if the gps beacon should be enabled, False otherwise
    ##@param gps_beacon_period, the period of the gps beacon (in seconds)
    def send_gps_beacon_command(self, gps_beacon_enable, gps_beacon_period):
        print('sending a gps beacon command to the Service')
        self.client.send_message('/gps_beacon',(gps_beacon_enable, gps_beacon_period))
        
    ##@param send the service a command to transmit one gps beacon immeadiatly
    def gps_one_shot_command(self):
        print('sending a gps one shot command to the service')
        self.client.send_message('/gps_one_shot',(True,))
    
    ###############################################################################
    ## Handlers for when the View Controller receives a message from the Service ##
    ###############################################################################
    
    ##@brief handler for when a TextMessage object is received from the service
    ##@param args, a list of values holding the TextMessage's contents
    def txt_msg_handler(self, address, *args):
        print('received text message from the service')
        txt_msg = TextMessageObject.unmarshal(args)
        self.ui.addMessageToUI(txt_msg)
    
    ##@brief handler for when a GPSMessage object is received from the service that was received by the radio
    ##@param args, a list of values holding the GPSMessage's contents
    def gps_msg_handler(self, address, *args):
        gps_msg = GPSMessageObject.unmarshal(args)
        if (gps_msg is not None):
            print('received gps message from the service: ' + gps_msg.src_callsign)
            self.ui.addGPSMessageToUI(gps_msg)
    
    ##@brief handler for when a GPSMessage object is received from the service this is my current location
    ##@param args, a list of values holding the GPSMessage's contents
    def my_gps_msg_handler(self, address, *args):
        gps_msg = GPSMessageObject.unmarshal(args)
        if (gps_msg is not None):
            self.ui.update_my_displayed_location(gps_msg.location)

    def ack_msg_handler(self, address, *args):
        print('received an acknoweledgement message from the service: '+ str(args))
        self.ui.addAckToUI((args[0],args[1],int(args[2])))       
    
    def transceiver_status_handler(self, address, *args):
        #print('received a status update from the service')
        self.ui.updateStatusIndicator(args[0])
        
    def tx_success_handler(self, address, *args):
        self.ui.update_tx_success_cnt(args[0])
        
    def tx_failure_handler(self, address, *args):
        self.ui.update_tx_failure_cnt(args[0])
    
    def rx_success_handler(self, address, *args):
        self.ui.update_rx_success_cnt(args[0])
    
    def rx_failure_handler(self, address, *args):
        self.ui.update_rx_failure_cnt(args[0])
        
    def test_handler(self, address, *args):
        print(args)

    ###############################################################################
    ############################ Thread Routines ##################################
    ###############################################################################
    
    def view_controller_func(self, server):
        #while (threading.currentThread().stopped() == False):
        server.serve_forever()  # Blocks forever