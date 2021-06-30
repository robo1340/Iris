import numpy as np
import io
import time
#import threading
#import queue
from queue import PriorityQueue
import view
import random
import threading
import time
import sys
import json

from IL2P import *

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import *

from kivy.logger import Logger as log

#IL2P constants

RAW_FRAME_MAXLEN = 3000 #the length in bytes of a raw IL2P payload, this valud is arbitrary at the moment
RAW_HEADER_LEN = 64 #the length of an IL2P header in bytes before removing its error correction symbols
#PREAMBLE_LEN = 1

BROADCAST_CALLSIGN = 6*' '

DEFAULT_RETRY_CNT = 3 #the number of times to re-transmit a frame that expects an ack
RETRANSMIT_TIME = 20 #the time in seconds to wait before re-transmitting a frame that expects an ack

TEXT_PID = 0
GPS_PID = 1

FORWARD_PRIORITY = 20 #the priority of a forwarded message
GPS_PRIORITY = 15 #the priority of a GPS message
TEXT_PRIORITY = 10 #the priority of a text message
ACK_PRIORITY = 5 #the priority of an acknowledgment

frame_engine_default = IL2P_Frame_Engine()

##class used to keep track of how many re-transmits have been made on a message requesting an ack        
class AckRetryObject():
    def __init__(self, msg, retry_cnt):
        self.msg = msg
        self.retry_cnt = retry_cnt
        self.time_since_last_retry = time.time()
    
    ##@brief decrement the retry_cnt member variable by one
    ##@returns returns the number of retries left
    def decrement(self):
        if (self.retry_cnt <= 0):
            return 0
        else:
            self.time_since_last_retry = time.time()
            self.retry_cnt = self.retry_cnt - 1
            return self.retry_cnt
            
    ##@brief check to see if the msg should be retransmitted      
    ##@return returns true if enough time has ellapsed, returns false otherwise
    def ready(self):
        rdy = ((time.time() - self.time_since_last_retry) > RETRANSMIT_TIME)
        tries_left = (self.retry_cnt > 0)
        return (rdy and tries_left)
    
##the main class that the rest of the program uses to interact with the IL2P link layer
class IL2P_API:

    def __init__(self, config, verbose=False):
        self.my_callsign = config.my_callsign
        
        self.engine = IL2P_Frame_Engine()
        
        self.service_controller = None #set this after the object is created

        self.msg_send_queue = PriorityQueue(50)
        #self.read_msg_send_queue = lambda : self.msg_send_queue.get()[1]
        
        self.pending_acks_lock = threading.Lock()
        self.pending_acks = {} #dictionary where the keys are tuples representing messages I sent that are pending acknowledgments, tuples are of the form (callsign, seq_num)
        
        self.forward_acks_lock = threading.Lock()
        self.forward_acks = AckSequenceList()
        self.enable_forwarding = True
        
        self.reader = IL2P_API.IL2P_Frame_Reader(verbose=verbose, frame_engine=self.engine)
        self.writer = IL2P_API.IL2P_Frame_Writer(verbose=verbose, frame_engine=self.engine)
        
        self.include_gps_in_ack = False
        
        #pending acknowledgments are stored in a dictionary where the key is a tuple containing the following elements in order:
        #   -the callsign of the station requesting an ack
        #   -the callsign of the station an ack is being requested from
        #   -the sequence number used to identify the ack
        self.ack_tx_key = lambda src,dst,seq : (src,dst,seq) #create a key for an ack from the transmitter's perspective
        self.ack_rx_key = lambda src,dst,seq : (dst,src,seq) #create a key for an ack from the receiver's perspective

    def setMyCallsign(self,new):
        self.my_callsign = new
    
    def readFrame(self):
        (header, payload) = self.reader.readFrame()
        if (header == None): #if the reader failed to decode the frame
            return False
        else:
            return self.processFrame(header, payload)
    
    def is_me(self, callsign):
        return (callsign == self.my_callsign)
    
    def processFrame(self, header, payload):
        #log.info('processFrame()')
        forward_msg = False #set to true if this message will be forwarded
        
        if (self.is_me(header.link_src_callsign)): #make sure I'm not the one who sent this
            #log.info('received my own message')
            return True
        
        if ((header.hops_remaining > 0) and (self.enable_forwarding)): #if this message is to be forwarded
            forward_msg = True
        
        #handle any forwarded acks contained in this message
        for seq in header.getForwardAckSequenceList():
            if (seq in self.pending_acks): #this is an acknowledgment for me
                #log.info('received a forwarded ack')
                self.pending_acks.pop(seq) #remove the ack from the pending acks dictionary
                forward_msg = False
                self.service_controller.send_ack_message(header.src_callsign, seq) #send the ack to the UI  
            else: #forward all received acknowledgements
                self.forward_acks.append(seq)
                self.service_controller.send_header_info(self.forward_acks)     
        
        if (header.request_double_ack or header.request_ack):
            log.info('message requesting an ack from %s and I am %s' % (header.dst_callsign, self.my_callsign))
            
            if (self.is_me(header.dst_callsign)): #this message requests an ack from me
                forward_msg = False #don't forward the message since it reached its detination
                
                #place the ack in circulation
                self.forward_acks.setMyAck(header.getMyAckSequence())
                self.service_controller.send_header_info(self.forward_acks)
                
                #log.info('message requesting ack from me')
                if (self.msg_send_queue.full() == True):
                    log.error('ERROR: frame send queue is full')
                else:
                    
                    payload_str = ''
                    if (self.include_gps_in_ack == True):
                        loc = self.service_controller.gps.getLocation()
                        loc_str = str(loc).replace('\'','\"') if (loc is not None) else ''
                        payload_str = loc_str
                    
                    log.info('creating ack')
                    ack_header = IL2P_Frame_Header(src_callsign=self.my_callsign, dst_callsign=header.src_callsign, \
                                   hops_remaining = header.hops, hops=header.hops, is_text_msg=False, is_beacon=self.include_gps_in_ack, \
                                   my_seq=header.getMyAckSequence(),\
                                   acks=self.forward_acks.getAcksBool(),\
                                   request_ack=False, request_double_ack=False, \
                                   payload_size=len(payload_str), \
                                   data=self.forward_acks.getAcksData())
                    ack_msg = MessageObject(header=ack_header, payload_str=payload_str, priority=ACK_PRIORITY)
                    self.msg_send_queue.put(ack_msg)
                    if (header.request_double_ack):
                        self.msg_send_queue.put(ack_msg)
            else: #this message is requesting an ack from someone else
                pass    
                
        #forward the message if the conditions are met
        if (forward_msg == True):
            if (self.msg_send_queue.full() == True):
                log.error('ERROR: frame send queue full while forwarding')
            else:
                log.info('forwarding message')
                new_hdr = IL2P_Frame_Header(src_callsign=header.src_callsign,\
                                            link_src_callsign=self.my_callsign,\
                                            dst_callsign=header.dst_callsign,\
                                            hops_remaining = header.hops_remaining-1, hops=header.hops,\
                                            is_text_msg=header.is_text_msg, is_beacon=header.is_beacon, \
                                            my_seq=header.my_seq, acks=header.acks,\
                                            request_ack=header.request_ack, request_double_ack=header.request_double_ack, \
                                            payload_size=header.payload_size, data=header.data)
                forward_msg = MessageObject(header=new_hdr, payload_str=payload.tobytes().decode('ascii','ignore'), priority=FORWARD_PRIORITY, forwarded=True)
                self.msg_send_queue.put(forward_msg)             
        
        if (header.is_text_msg == True):
            #log.info('Text Message Received, src=%s, dst=%s, msg=%s' % (header.src_callsign, header.dst_callsign, payload))
            
            if (header.payload_size > 0): #send all messages with payloads to the output queue
                msg = MessageObject(header=header, payload_str=payload.tobytes().decode('ascii','ignore'))
                self.service_controller.send_txt_message(msg) #send the message to the ui
            return True
            
        elif (header.is_beacon == True):
            try:
                self.service_controller.send_gps_message(MessageObject(header=header, payload_str=payload.tobytes().decode('ascii','ignore')))
                return True   
            except BaseException:
                log.warning('WARNING: failed to decode payload of a GPS message')
                return False          
    
    ## @brief convert a MessageObject to a Frame and return the raw frame to be transmitted
    ## @param msg - The MessageObject
    def msgToFrame(self, msg):
        if (msg.forwarded == False):
            if (msg.header.request_double_ack or msg.header.request_ack):
                if (msg.get_ack_seq() is not None):
                    self.pending_acks[msg.get_ack_seq()] = AckRetryObject(msg,DEFAULT_RETRY_CNT) #create a new entry in the dictionary 
        return self.writer.getFrameFromMessage(msg)
    
    ##@brief check to see if there is a frame to transmit right now
    ##@return - Returns true when there is a frame to send, returns false otherwise
    def isTransmissionPending(self):
        if (self.msg_send_queue.empty() == False):
            #log.info('Transmission Pending')
            return True
        elif (len(self.pending_acks) == 0):
            return False
        else:
            toReturn = False
            for key, retry in self.pending_acks.items():
                if (retry.ready() == True):
                    toReturn = True
                    break
            return toReturn
            
    ##@brief return the next Frame to be transmitted
    ##@return - Returns a tuple containing the next frame to be transmitted and the carrier length to use
    ## New Frames are prioritized, then re-transmissions
    ## If there is nothing to transmit, returns (None,0)
    def getNextFrameToTransmit(self):
        if (self.msg_send_queue.empty() == False):
            msg = self.msg_send_queue.get()#[1]
            carrier_len = msg.carrier_len
            return (self.msgToFrame(msg),carrier_len)
        elif (len(self.pending_acks) == 0):
            return (None,0)
        else:
            toPop = None
            toReturn = None
            carrier_len = 0
            for key, retry in self.pending_acks.items():
                if (retry.ready() == True):
                    #log.info("key " + str(key))
                    if (retry.decrement() == 0): #if the remaining number of tries is zero, do not re-transmit 
                        self.service_controller.send_retry_message(key, -1)
                        continue
                    self.service_controller.send_retry_message(key, retry.retry_cnt-1)
                    toReturn = self.writer.getFrameFromMessage(retry.msg)
                    carrier_len = retry.msg.carrier_len
                    #log.info(carrier_len)
            if (toPop != None):
                self.pending_acks.pop(toPop)
            return (toReturn,carrier_len)

    ##class used to read bytes from the phy layer and detect when a valid Frame is being received
    class IL2P_Frame_Reader:

        def __init__(self, verbose=False, frame_engine=frame_engine_default):
            self.src = None
            self.verbose = verbose
            
            self.frame_engine = frame_engine
        
        ##@brief sets the data source to be used by the IL2P_Frame_Reader and starts the frame reading thread
        ##@param src a ReceiverPipe object that will be filled with decoded bytes by the phy layer
        def setSource(self, src):
            self.src = src
        
        ##@brief function to be called when the phy layer has a full frame ready for the link layer
        ##@return returns a tuple containing the message header and payload bytes when the message is received, returns None otherwise
        def readFrame(self):
            ind = 0
            raw_frame = np.zeros(RAW_FRAME_MAXLEN,dtype=np.uint8)

            while(True):
                if (self.src.recv_queue.empty() == False) and (ind < RAW_FRAME_MAXLEN): #if the queue isn't empty
                    ele = self.src.recv_queue.get() #get the next element from the queue
                    if (type(ele) is not int): #unknown type detected in queue
                        log.error('ERROR: Unknown type in receive queue')
                        continue 
                    else:
                        raw_frame[ind] = ele
                        ind+=1  
                else: #decode the frame
                    log.debug('raw frame received: 0x%s', raw_frame[0:ind].tobytes().hex())
                    try:
                        (header, payload_decode_success, payload_bytes) = self.frame_engine.decode_frame(raw_frame)
                        #log.info(header.getInfoString())
                        #log.info(payload_bytes.tobytes()) #need to be doing something with bytes received    
                        
                        if (payload_decode_success == False):
                            log.warning('WARNING: the payload was not completely decoded successfully, the header was decoded though')
                            
                        return (header, payload_bytes)
                        
                    except exceptions.IL2PHeaderDecodeError:
                        log.warning('Failed to decode a frame header, the rest of the frame will be discarded')
                        return (None,'')
                    except BaseException:
                        log.warning('Failed to decode frame')
                        return (None,'')
                    break
            return (None,'')

    class IL2P_Frame_Writer:
        def __init__(self, verbose=False, frame_engine=frame_engine_default):
            self.verbose = verbose
            self.frame_engine = frame_engine
        
        ##@brief convert a Message Object to a frame ready to be sent
        ##@param msg a MessageObject to be converted into a frame
        def getFrameFromMessage(self, msg):
            #frame = self.frame_engine.encode_frame(msg.header, np.frombuffer(msg.payload_str.encode(), dtype=np.uint8))
             #frame_engine.encode_frame(header,     np.frombuffer( msg_str.encode(),dtype=np.uint8))
            frame = self.frame_engine.encode_frame(msg.header, np.frombuffer(msg.payload_str.encode(),dtype=np.uint8))
            toReturn = frame.tobytes()
            log.debug('raw frame to be sent: 0x%s',toReturn.hex())
            return toReturn                   


