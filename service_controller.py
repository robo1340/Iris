import threading
import time
import logging
import queue
import numpy as np
import time
import sched
import sys
import functools
import zmq
import os
import pickle
from datetime import datetime

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import *
import common
from common import exception_suppressor
import queue
import IL2P_API
from IL2P import IL2P_Frame_Header
from view import view_controller as view_c

from kivy.logger import Logger as log

NUM_PUBS = 2
BASE_PORT = 5555

TXT_MSG_RX = "/txt_msg_rx"
GPS_MSG = "/gps_msg"
WAYPOINT_MSG = "/waypoint_msg"
MY_GPS_MSG = '/my_gps_msg'
ACK_MSG = '/ack_msg'
STATUS_INDICATOR = '/status_indicator'
TX_SUCCESS = '/tx_success'
TX_FAILURE = '/tx_failure'
RX_SUCCESS = '/rx_success'
RX_FAILURE = '/rx_failure'
GPS_LOCK_ACHIEVED = '/gps_lock_achieved'
SIGNAL_STRENGTH = '/signal_strength'
RETRY_MSG = '/retry_msg'
HEADER_INFO = '/header_info'

class ServiceController():

    def __init__(self, il2p, config, gps=None, osm=None):
        self.il2p = il2p
        self.osm = osm
        self.isStopped = False

        self.context = zmq.Context() #context used by the subscriber
        self.pubs = []
        self.bind_addrs = common.generate_bind_addr(NUM_PUBS, BASE_PORT)
        
        self.pubs = []
        for addr in self.bind_addrs:
            self.pubs.append(None)
        
        self.sub = self.context.socket(zmq.SUB)
        self.sub.subscribe('')
        self.sub.connect("tcp://127.0.0.1:8000")
        
        self.tx_queue = queue.Queue()
        
        self.gps_beacon_enable = config.gps_beacon_enable
        self.gps_beacon_period = config.gps_beacon_period
        self.gps_next_beacon = time.time() if self.gps_beacon_enable else -1
        
        self.waypoint_beacon_enable = config.waypoint_beacon_enable
        self.waypoint_beacon_period = config.waypoint_beacon_period
        self.waypoint_next_beacon = time.time() if self.waypoint_beacon_enable else -1
        
        self.carrier_length = config.carrier_length
        
        self.hops = 0
        #self.enable_vibration = config.enable_vibration
        
        self.stats = common.Stats()
        
        self.gps = gps
        if (self.gps != None):
            self.gps.start(self)
        
        self.thread = common.StoppableThread(target = self.service_controller_func, args=(0,))
        self.thread.start()
        
        self.pub_thread = common.StoppableThread(target = self.service_pub_func, args=(0,))
        self.pub_thread.start()
        
        self.gps_thread = common.StoppableThread(target = self.gps_beacon_thread_func, args=(0,))
        self.gps_thread.start()
        
        self.waypoint_thread = common.StoppableThread(target = self.waypoint_beacon_thread_func, args=(0,))
        self.waypoint_thread.start()
        
    ###############################################################################
    ## Handlers for when the service receives a message from the View Controller ##
    ###############################################################################
    
    def service_controller_func(self, arg):
        sub = self.context.socket(zmq.SUB)
        sub.subscribe('')
        connect_addrs = common.generate_connect_addr(view_c.NUM_PUBS, view_c.BASE_PORT)
        for addr in connect_addrs:
            sub.connect(addr)
        
        poller = zmq.Poller()
        poller.register(sub, zmq.POLLIN)

        while not self.stopped():
            try:
                socks = dict(poller.poll(timeout=1000))
                if sub in socks and socks[sub] == zmq.POLLIN:
                    header = sub.recv_string()
                    payload = sub.recv_pyobj()

                    if (header == view_c.TXT_MSG_TX):
                        self.txt_msg_handler(payload)
                    elif (header == view_c.MY_CALLSIGN):
                        self.my_callsign_handler(payload)
                    elif (header == view_c.GPS_BEACON_CMD):
                        self.gps_beacon_handler(payload)
                    elif (header == view_c.WAYPOINT_BEACON_CMD):
                        self.waypoint_beacon_handler(payload)
                    elif (header == view_c.ENABLE_FORWARDING_CMD):
                        self.enable_forwarding_handler(payload)
                    elif (header == view_c.GPS_ONE_SHOT):
                        self.gps_one_shot_handler()
                    elif (header == view_c.WAYPOINT_ONE_SHOT):
                        self.waypoint_one_shot_handler()
                    elif (header == view_c.STOP):
                        self.stop_handler()
                    elif (header == view_c.HOPS):
                        self.hops_update_handler(payload)
                    elif (header == view_c.FORCE_SYNC_OSMAND):
                        threading.Timer(0, self.force_sync_osmand_handler).start()
                    elif (header == view_c.CLEAR_OSMAND_CONTACTS):
                        threading.Timer(0, self.clear_osmand_contacts_handler).start()   
                    elif (header == view_c.CLEAR_OSMAND_WAYPOINTS):
                        threading.Timer(0, self.clear_osmand_waypoints_handler).start()
                    elif (header == view_c.INCLUDE_GPS_IN_ACK):
                        self.include_gps_in_ack_handler(payload)
                    #elif (header == view_c.ENABLE_VIBRATION):
                    #    self.enable_vibration_handler(payload)
                    else:
                        log.info('No handler found for topic %s' % (header))
                
            except zmq.ZMQError:
                log.error("A ZMQ specific error occurred in the service controller receiver thread")
            except BaseException:
                log.error("Error in service controller zmq receiver thread")
    
    def service_pub_func(self, arg):
        self.pubs[0] = self.context.socket(zmq.PUB)
        self.pubs[0].bind(self.bind_addrs[0])
        
        self.pubs[1] = self.context.socket(zmq.PUB)
        self.pubs[1].set(zmq.SNDHWM, 5)
        self.pubs[1].bind(self.bind_addrs[1])
        
        while not self.stopped():
            try:
                (pub_ind, env, payload) = self.tx_queue.get(block=True, timeout=1)
                self.pubs[pub_ind].send_string(env, flags=zmq.SNDMORE)
                self.pubs[pub_ind].send_pyobj(payload)
            except queue.Empty:
                pass
            
            except BaseException as ex:
                log.error("Error in service controller zmq publisher thread")
                log.error(ex)
        
    ## @brief callback for when the View Controller sends a UDP datagram containing a text message to be transmitted
    def txt_msg_handler(self, txt_msg):
        log.debug('service ctrl txt_msg_handler()')
        self.il2p.msg_send_queue.put(txt_msg)
    
    ## @brief callback for when the View Controller sends a new callsign
    def my_callsign_handler(self, my_callsign):
        log.debug('my callsign received from View Controller')
        self.il2p.setMyCallsign(my_callsign)
    
    def gps_beacon_handler(self, args):
        #self.osm.set_map_location(34,70)
        log.debug('gps beacon settings received from View Controller: %s, %d' % (str(args[0]), args[1]))
        self.gps_beacon_enable = args[0]
        self.gps_beacon_period = args[1]
    
    def waypoint_beacon_handler(self, args):
        log.debug('waypoint beacon settings received from View Controller: %s, %d' % (str(args[0]), args[1]))
        self.waypoint_beacon_enable = args[0]
        self.waypoint_beacon_period = args[1]
    
    def enable_forwarding_handler(self, enable_forwarding):
        self.il2p.enable_forwarding = enable_forwarding
    
    def gps_one_shot_handler(self):
        log.debug('gps one shot command received from View Controller')
        self.transmit_gps_beacon()
    
    def waypoint_one_shot_handler(self):
        log.info('waypoint one shot command received from View Controller')
        self.transmit_waypoint_beacon()
    
    def stop_handler(self):
        log.debug('stopping the service threads')
        self.isStopped = True
        #self.stop()
    
    def hops_update_handler(self, hops):
        self.hops = hops
    
    def force_sync_osmand_handler(self):
        self.osm.refreshContacts()
        self.osm.refresh_waypoints()
        
    def clear_osmand_contacts_handler(self):
        self.osm.eraseContacts()
    
    def clear_osmand_waypoints_handler(self):
        self.osm.erase_waypoints()
    
    def include_gps_in_ack_handler(self, include_gps):
        self.il2p.include_gps_in_ack = include_gps
    
    #def enable_vibration_handler(self, enable_vibration):
    #    self.enable_vibration = enable_vibration
    
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
    
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_txt_message(self, msg):
        log.debug('sending text message to the View Controller')
        msg.mark_time()
        self.tx_queue.put((0,TXT_MSG_RX,msg), block=False)
    
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_gps_message(self, msg):
        log.debug('sending gps message to View Controller')
        gps_msg = msg.get_location()
        if (gps_msg is None):
            log.warning('a non-gps message ended up in a gps message handler')
        else:
            gps_msg.mark_time() #record the current time into the gps message
            self.tx_queue.put((0,GPS_MSG,gps_msg), block=False)

            if (self.osm.isStarted() and (gps_msg.src_callsign != self.il2p.my_callsign)):
            #if ((self.osm is not None) and (gps_msg.src_callsign != self.il2p.my_callsign)):
                self.osm.placeContact(gps_msg.lat(), gps_msg.lon(), gps_msg.src_callsign, gps_msg.time_str+'\n'+gps_msg.getInfoString())
    
    ##@param msg a MessageObject whose payload contains a waypoint
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_waypoint_message(self, msg):
        log.debug('sending waypoint to View Controller')
        waypoint_msg = msg.get_waypoints()
        
        if waypoint_msg is None:
            log.warning('a non-waypoint message ended up in a waypoint message handler')
        else:
            waypoint_msg.mark_time() #record the current time into the message
            self.tx_queue.put((0,WAYPOINT_MSG,waypoint_msg), block=False)

            if (self.osm.isStarted() and (waypoint_msg.src_callsign != self.il2p.my_callsign)): #place the waypoints in OsmAnd
                self.osm.place_waypoints(waypoint_msg.src_callsign, waypoint_msg.waypoints)
    
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_header_info(self, info):
        log.debug('updating header info')
        self.tx_queue.put((0,HEADER_INFO,info), block=False)
    
    ##@brief send the View Controller my current gps location contained in a GPSMessage object
    ##@param gps_msg a GPSMessage object
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_my_gps_message(self, gps_msg):
        log.debug('sending my gps message to View Controller')
        self.tx_queue.put((0,MY_GPS_MSG,gps_msg), block=False)

    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_ack_message(self, ack_callsign, ack_key):
        log.debug('sending message acknowledgment to View Controller')
        self.tx_queue.put((0,ACK_MSG, (ack_callsign, ack_key)), block=False)
    
    def send_status(self, status):
        with open('./' + common.STATUS_IND_FILE, 'wb') as f:
            pickle.dump(status, f)
  
    #tx_failure, tx_success, rx_failure, rx_success
    def send_statistic(self, type_str, value):
        if (type_str == 'tx_success'):
            self.stats.txs = value
        elif (type_str == 'tx_failure'):
            self.stats.txf = value
        elif (type_str == 'rx_success'):
            self.stats.rxs = value
        elif (type_str == 'rx_failure'):
            self.stats.rxf = value
            
        with open('./' + common.STATISTICS_FILE, 'wb') as f:
            pickle.dump(self.stats, f)
    
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_gps_lock_achieved(self, isLockAchieved):
        self.tx_queue.put((0,GPS_LOCK_ACHIEVED,isLockAchieved), block=False)
    
    def send_signal_strength(self, signal_strength):
        if (signal_strength < 0):
            return
        else:
            with open('./' + common.SIGNAL_STRENGTH_FILE, 'wb') as f:
                pickle.dump(signal_strength, f)
    
    @exception_suppressor(e=queue.Full, msg='service controller tx queue is full')
    def send_retry_message(self, ack_key, remaining_retries):
        log.debug('sending retry message to View Controller')
        self.tx_queue.put((0,RETRY_MSG,(ack_key, remaining_retries)), block=False)
    
    ###############################################################################
    ############### Methods for controlling the il2p link layer ###################
    ###############################################################################
    ############################### GPS Beacons ###################################
    ###############################################################################
    
    def stopped(self):
        return self.isStopped
    
    def gps_beacon_thread_func(self, args):
        while not self.stopped():
            if (self.gps_beacon_enable):
                if (self.gps_next_beacon == -1):
                    T = self.gps_beacon_period
                    self.gps_next_beacon = time.time() + T + 0.1*np.random.uniform(-T,T)
                elif (time.time() > self.gps_next_beacon):
                    self.transmit_gps_beacon()
                    T = self.gps_beacon_period
                    self.gps_next_beacon = time.time() + T + 0.1*np.random.uniform(-T,T)
            else:
                self.gps_next_beacon = -1
            time.sleep(1)
    
    @exception_suppressor(msg='exception caught in transmit_gps_beacon()')
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
                                       hops_remaining=self.hops, hops=self.hops, is_text_msg=False, is_beacon=True, \
                                       #hops_remaining=0, hops=0, is_text_msg=False, is_beacon=True, \
                                       my_seq = self.il2p.forward_acks.my_ack,\
                                       acks=self.il2p.forward_acks.getAcksBool(), \
                                       request_ack=False, request_double_ack=False, \
                                       payload_size=len(loc_str), \
                                       data=self.il2p.forward_acks.getAcksData())
            
            gps_msg = MessageObject(header=gps_hdr, payload_str=loc_str, priority=IL2P_API.GPS_PRIORITY)
            
            self.send_my_gps_message(GPSMessageObject(src_callsign=self.il2p.my_callsign, location=loc)) #send my gps location to the View Controller so it can be displayed
            
            self.il2p.msg_send_queue.put(gps_msg) #send my gps location to the il2p transceiver so that it can be transmitted
     
    ###############################################################################
    ############################ Waypoint Beacons #################################
    ###############################################################################

    def waypoint_beacon_thread_func(self, args):
        while not self.stopped():
            if (self.waypoint_beacon_enable):
                if (self.waypoint_next_beacon == -1):
                    T = self.waypoint_beacon_period
                    self.waypoint_next_beacon = time.time() + T + 0.1*np.random.uniform(-T,T)
                elif (time.time() > self.waypoint_next_beacon):
                    self.transmit_waypoint_beacon()
                    T = self.waypoint_beacon_period
                    self.waypoint_next_beacon = time.time() + T + 0.1*np.random.uniform(-T,T)
            else:
                self.waypoint_next_beacon = -1
            time.sleep(1)
    
    @exception_suppressor(msg='exception caught in transmit_waypoint_beacon()')
    def transmit_waypoint_beacon(self):
        if not os.path.isfile('./' + common.MY_WAYPOINTS_FILE):
            log.info('WARNINGS: No Waypoints Set yet')
        else:
            with open('./' + common.MY_WAYPOINTS_FILE, 'rb') as f:
                waypoints = pickle.load(f)
                if (waypoints is None):
                    log.warning('WARNING: Failed to load waypoints file')
                    return

                waypoints_str = str(waypoints).replace('\'','\"')
                #log.info('WAYPOINTS to send: \"%s\"' % (waypoints_str,))
                
                #waypoint_header = IL2P_Frame_Header(src_callsign='BAYWAX', dst_callsign='', \
                waypoint_header = IL2P_Frame_Header(src_callsign=self.il2p.my_callsign, dst_callsign='', \
                                           hops_remaining=self.hops, hops=self.hops, is_text_msg=False, is_beacon=False, is_waypoint=True, \
                                           #hops_remaining=0, hops=0, is_text_msg=False, is_beacon=True, \
                                           my_seq = self.il2p.forward_acks.my_ack,\
                                           acks=self.il2p.forward_acks.getAcksBool(), \
                                           request_ack=False, request_double_ack=False, \
                                           payload_size=len(waypoints_str), \
                                           data=self.il2p.forward_acks.getAcksData())

                waypoint_msg = MessageObject(header=waypoint_header, payload_str=waypoints_str, priority=IL2P_API.GPS_PRIORITY)

                self.il2p.msg_send_queue.put(waypoint_msg) #send my gps location to the il2p transceiver so that it can be transmitted
                
