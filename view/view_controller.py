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
import service_controller as service

from kivy.logger import Logger as log
from kivy.clock import Clock

NUM_PUBS = 1
BASE_PORT = 8000

#VIEW_PUB_IND = 0
#    service_stop_command
#    send_my_callsign
#    send_txt_message
#    gps_one_shot_command
#    send_gps_beacon_command

#pub topics
TXT_MSG_TX = "/txt_msg_tx"
MY_CALLSIGN = "/my_callsign"
GPS_BEACON_CMD = "/gps_beacon"
GPS_ONE_SHOT = '/gps_one_shot'
STOP = '/stop'
HOPS = '/hops'
FORCE_SYNC_OSMAND = '/force_sync_osmand'
CLEAR_OSMAND_CONTACTS = '/clear_osmand_contacts'

#def generate_bind_addr(num, base_port):
#def generate_connect_addr(num, base_port):

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
        self.pubs = []
        self.bind_addrs = common.generate_bind_addr(NUM_PUBS, BASE_PORT)
        
        for addr in self.bind_addrs:
            self.pubs.append(None)
        
        self.tx_queue = queue.Queue()
    
        self.ui = None
        self.contacts_dict = {} #a dictionary describing the current gps contacts that have been placed
        #keys are the callsign string, values are a GPSMessaageObject
        
        self.stopped = False
    
        #self.thread = common.StoppableThread(target = self.view_controller_func, args=(self.server,))
        self.thread = common.StoppableThread(target = self.view_controller_func, args=(0,))
        self.thread.start()
        
        self.pub_thread = common.StoppableThread(target = self.view_pub_func, args=(0,))
        self.pub_thread.start()
    
    def stop(self):
        self.stopped = True
    
    #the thread function
    def view_controller_func(self,arg):
        #sub = self.context.socket(zmq.SUB)
        #sub.subscribe('')
        poller = zmq.Poller()
        connect_addrs = common.generate_connect_addr(service.NUM_PUBS, service.BASE_PORT)
        for addr in connect_addrs:
            sub = self.context.socket(zmq.SUB)
            sub.subscribe('')
            sub.connect(addr)
            poller.register(sub, zmq.POLLIN)
        
        while not self.stopped:
            try:
                socks = dict(poller.poll(timeout=1000))
                for sub in socks:
                    if socks[sub] != zmq.POLLIN:
                        continue
                #if sub in socks and socks[sub] == zmq.POLLIN:
                    header = sub.recv_string()
                    payload = sub.recv_pyobj()
                    #log.info("header %s" % (header))

                    if (header == service.TXT_MSG_RX):
                        self.txt_msg_handler(payload)
                    elif (header == service.MY_GPS_MSG):
                        self.my_gps_msg_handler(payload)
                    elif (header == service.GPS_MSG):
                        self.gps_msg_handler(payload)
                    elif (header == service.ACK_MSG):
                        self.ack_msg_handler(payload)
                    elif (header == service.STATUS_INDICATOR):
                        self.transceiver_status_handler(payload)
                    elif (header == service.TX_SUCCESS):
                        self.tx_success_handler(payload)
                    elif (header == service.TX_FAILURE):
                        self.tx_failure_handler(payload)
                    elif (header == service.RX_SUCCESS):
                        self.rx_success_handler(payload)
                    elif (header == service.RX_FAILURE):
                        self.rx_failure_handler(payload)
                    elif (header == service.GPS_LOCK_ACHIEVED):
                        self.gps_lock_achieved_hander(payload)
                    elif (header == service.SIGNAL_STRENGTH):
                        self.signal_strength_handler(payload)  
                    elif (header == service.RETRY_MSG):
                        self.retry_msg_handler(payload)
                    elif (header == service.HEADER_INFO):
                        self.header_info_handler(payload)
                    else:
                        log.info('No handler found for topic %s' % (header))                 
                    
            
            except zmq.ZMQError:
                log.error("A ZMQ specific error occurred in the view controller receiver thread")
            except BaseException:
                log.error("Error in view controller zmq receiver thread")
                log.info("header %s, payload %s" % (header, str(payload)))
        log.info('view controller receiver ended==========================')

    def view_pub_func(self, arg):
        self.pubs[0] = self.context.socket(zmq.PUB)
        self.pubs[0].bind(self.bind_addrs[0])
        
        while not self.stopped:
            try:
                (pub_ind, env, payload) = self.tx_queue.get(block=True, timeout=1)
                self.pubs[pub_ind].send_string(env, flags=zmq.SNDMORE)
                self.pubs[pub_ind].send_pyobj(payload)
            except queue.Empty:
                pass
            except BaseException:
                log.error("Error in view controller zmq publisher thread")
        log.info('view controller publisher ended==========================')
        
    ###############################################################################
    ############### Methods for sending messages to the Service ###################
    ###############################################################################
    
    ## @brief send a text message to the service to be transmitted
    def send_txt_message(self, txt_msg):
        try:
            self.tx_queue.put((0,TXT_MSG_TX,txt_msg), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
        log.info('view ctrl send_txt_message()')
    
    ## @brief send a new callsign entered by the user to the service
    def send_my_callsign(self, my_callsign):
        try:
            self.tx_queue.put((0,MY_CALLSIGN,my_callsign), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
    
    ##@brief send the service a new gps beacon state and gps beacon period
    ##@param gps_beacon_enable True if the gps beacon should be enabled, False otherwise
    ##@param gps_beacon_period, the period of the gps beacon (in seconds)
    def send_gps_beacon_command(self, gps_beacon_enable, gps_beacon_period):
        try:
            self.tx_queue.put((0,GPS_BEACON_CMD,(gps_beacon_enable, gps_beacon_period)), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
        log.info('sending a gps beacon command to the Service')
        
    ##@brief send the service a command to transmit one gps beacon immeadiatly
    def gps_one_shot_command(self):
        log.debug('sending a gps one shot command to the service')
        try:
            self.tx_queue.put((0,GPS_ONE_SHOT,''), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
        
    ##@brief send the service a command to shutdown
    def service_stop_command(self):
        try:
            self.tx_queue.put((0,STOP,''), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
        log.debug('view controller shutting down the service')
    
    def update_hops(self, hops):
        try:
            self.tx_queue.put((0,HOPS,hops), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
    
    def force_sync_osmand(self):
        try:
            self.tx_queue.put((0,FORCE_SYNC_OSMAND,''), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
        
    def clear_osmand_contacts(self):
        try:
            self.tx_queue.put((0,CLEAR_OSMAND_CONTACTS,''), block=False)
        except queue.Full:
                log.warning('view controller tx queue is full')
    
    
    ###############################################################################
    ## Handlers for when the View Controller receives a message from the Service ##
    ###############################################################################
    
    ##@brief handler for when a TextMessage object is received from the service
    def txt_msg_handler(self, msg):
        log.debug('received text message from the service')
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
    def gps_msg_handler(self, gps_msg):
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
    def my_gps_msg_handler(self, gps_msg):
        if (gps_msg is not None):
            Clock.schedule_once(functools.partial(self.ui.update_my_displayed_location, gps_msg.location), 0)
    
    def ack_msg_handler(self, args):
        ack_callsign = args[0]
        ack_key = args[1]
        toast('Ack received from ' + str(ack_callsign))
        vibrator.pattern(pattern=ack_vibe_pattern)
        Clock.schedule_once(functools.partial(self.ui.addAckToUI, ack_key), 0)  
        
    @exception_suppressor
    def transceiver_status_handler(self, status):
        log.debug('received a status update from the service')
        Clock.schedule_once(functools.partial(self.ui.updateStatusIndicator, status), 0)
        
    def tx_success_handler(self, arg):
        Clock.schedule_once(functools.partial(self.ui.update_tx_success_cnt, arg), 0)
        
    def tx_failure_handler(self, arg):
        Clock.schedule_once(functools.partial(self.ui.update_tx_failure_cnt, arg), 0)
    
    def rx_success_handler(self, arg):
        Clock.schedule_once(functools.partial(self.ui.update_rx_success_cnt, arg), 0)
    
    def rx_failure_handler(self, arg):
        Clock.schedule_once(functools.partial(self.ui.update_rx_failure_cnt, arg), 0)
        
    def gps_lock_achieved_hander(self, lock_achieved):
        if (not lock_achieved):
            return
        log.debug('gps lock achieved')
        Clock.schedule_once(functools.partial(self.ui.notifyGPSLockAchieved), 0) #update the ui elements to show gps lock achieved
    
    #@exception_suppressor
    def signal_strength_handler(self, signal_strength):
        #log.debug('view controller received signal strength- ' + str(args[0]))
        Clock.schedule_once(functools.partial(self.ui.update_signal_strength, signal_strength), 0)
    
    #args[0]=ack_key
    #args[1] = remaining_retries
    def retry_msg_handler(self, args):
        Clock.schedule_once(functools.partial(self.ui.updateRetryCount, args[0], args[1]), 0)
        log.debug('received a retry message from the service controller')
        #Clock.schedule_once(functools.partial(self.ui.updateRetryCount, int(args[0]), int(args[1]) ), 0) 
        
    def header_info_handler(self, header_info):
        Clock.schedule_once(functools.partial(self.ui.updateHeaderInfo, header_info), 0)
