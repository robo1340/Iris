import numpy as np
import io
import time
#import threading
import queue
import view
import random
import threading
import time
import sys
import json

from IL2P import *

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject, GPSMessageObject

log = logging.getLogger(__name__)

#IL2P constants

RAW_FRAME_MAXLEN = 1299 #the length in bytes of a raw IL2P header before removing error correction symbols and including the header and sync byte
RAW_HEADER_LEN = 25 #the length of an IL2P header in bytes before removing its error correction symbols
PREAMBLE_LEN = 1

BROADCAST_CALLSIGN = 6*' '

DEFAULT_RETRY_CNT = 3 #the number of times to re-transmit a frame that expects an ack
RETRANSMIT_TIME = 15 #the time in seconds to wait before re-transmitting a frame that expects an ack

TEXT_PID = 0
GPS_PID = 1


frame_engine_default = IL2P_Frame_Engine()

##class used to keep track of how many re-transmits have been made on a message requesting an ack        
class AckRetryObject():
    def __init__(self, msg, retry_cnt):
        self.msg = msg
        self.retry_cnt = retry_cnt - 1
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

    def __init__(self, ini_config, verbose=False, msg_send_queue=None):
        DEFAULT_RETRY_CNT = ini_config['MAIN']['ack_retries']
        RETRANSMIT_TIME = ini_config['MAIN']['ack_timeout']
    
        self.my_callsign = ini_config['MAIN']['my_callsign']
        
        self.engine = IL2P_Frame_Engine()
        
        self.service_controller = None #set this after the object is created
        #self.msg_output_queue = msg_output_queue
        #self.ack_output_queue = ack_output_queue
        self.msg_send_queue = msg_send_queue
        
        self.pending_acks_lock = threading.Lock()
        self.pending_acks = {} #dictionary where the keys are tuples representing messages I sent that are pending acknowledgments, tuples are of the form (callsign, seq_num)
        
        self.reader = IL2P_API.IL2P_Frame_Reader(verbose=verbose, frame_engine=self.engine)
        self.writer = IL2P_API.IL2P_Frame_Writer(verbose=verbose, frame_engine=self.engine)
        
        #pending acknowledgments are stored in a dictionary where the key is a tuple containing the following elements in order:
        #   -the callsign of the station requesting an ack
        #   -the callsign of the station an ack is being requested from
        #   -the sequence number used to identify the ack
        self.ack_tx_key = lambda src,dst,seq : (src,dst,seq) #create a key for an ack from the transmitter's perspective
        self.ack_rx_key = lambda src,dst,seq : (dst,src,seq) #create a key for an ack from the receiver's perspective
        
        #acknowledgments are identified by the 1-bit ui field in the header and the length of the payload:
        # 1) A frame with the ui field set to 1 and a payload length greater than 0 is requesting an acknowledgment from the destination callsign
        # 2) A frame with the ui field set to 1 and no payload is an acknowledgment responding to case 1 above
        # 3) A frame with the ui field is not an acknowledgment and is not requesting an acknowledgment
        # 4) (special case) When ui is set to 1 and the destination callsign is the broadcast callsign, the sender will not re-transmit the message if no ack is received
        self.isAck          = lambda hdr,pld : ((hdr.ui == 1) and (len(pld)==0))
        self.requestsAck    = lambda hdr,pld : ((hdr.ui == 1) and (len(pld) > 0))

    def setMyCallsign(self,new):
        self.my_callsign = new
    
    def readFrame(self):
        (header, payload) = self.reader.readFrame()
        
        if (header == None): #if the reader failed to decode the frame
            return False
        
        if (header.pid == TEXT_PID):
            src = header.src_callsign
            dst = header.dst_callsign
            ack = True if (header.ui == 1) else False
            seq = header.control
            msg = payload.tobytes().decode('ascii','ignore') #convert payload bytes to a string while ignoring all non-ascii characters
            
            #now need to add handling of acks here
            if (self.isAck(header,payload) == True): #the message received is an acknowledgment
                if (dst == self.my_callsign): #this is an acknowledgment for me
                    self.pending_acks_lock.acquire()
                    ack_key = self.ack_rx_key(src,dst,seq)
                    if (ack_key in self.pending_acks): #if I have been expecting this ack
                        self.pending_acks.pop(ack_key) #remove the ack from the pending acks dictionary
                        self.service_controller.send_ack_message(ack_key) #send the ack to the UI
                        #self.ack_output_queue.put(ack_key)
                    self.pending_acks_lock.release()
                        
            elif (self.requestsAck(header,payload) == True): #len(msg) > 0, the message received is requesting an acknowledgment
                if ((dst == self.my_callsign) or (dst == BROADCAST_CALLSIGN)): #this message is addressed to me (or is a broadcast) and requests an ack. I need to send an ack
                    
                    if (self.msg_send_queue.full() == True):
                        log.error('ERROR: frame send queue is full')
                    else:
                        ack_msg = TextMessageObject(msg_str='', src_callsign=self.my_callsign, dst_callsign=src, expectAck=True, seq_num=seq) #create the ack message to be sent
                        self.msg_send_queue.put(ack_msg) #put the message on a queue to be sent to the radio
            
            if (self.isAck(header,payload) == False): #send all messages to the output queue except those which are acks
                received_txt_msg = TextMessageObject(msg, src, dst, ack, seq)
                self.service_controller.send_txt_message(received_txt_msg) #send the message to the UI
                #self.msg_output_queue.put(received_txt_msg) #place the received text message into receive queue
            return True
            
        elif (header.pid == GPS_PID):
            try:
                gps_dict = json.loads( payload.tobytes().decode('ascii','ignore') ) #convert payload bytes to a dictionary while ignoring all non-ascii characters
                log.info(gps_dict['lat'])
                log.info(gps_dict['lon'])
                log.info(gps_dict['speed'])
                log.info(gps_dict['bearing'])
                log.info(gps_dict['altitude'])
                log.info(gps_dict['accuracy'])
                received_gps_msg = GPSMessageObject(gps_dict, header.src_callsign)
                self.service_controller.send_gps_message(received_gps_msg) #send the message to the UI
                #self.msg_output_queue.put(received_gps_msg) #place the received gps message into the receive queue
                return True   
            except BaseException:
                log.warning('WARNING: failed to decode payload of a GPS message')
                return False
            
    
    ## @brief convert a TextMessageObject to a Frame and return the raw frame to be transmitted
    ## @param msg - The TextMessageObject or GPSMessageObject to be sent
    def msgToFrame(self, msg):
        if (isinstance(msg,TextMessageObject)): 
            if (msg.expectAck == True):
                self.pending_acks_lock.acquire()
                ack = self.ack_tx_key(msg.src_callsign,msg.dst_callsign,msg.seq_num)
                if ((msg.dst_callsign is not BROADCAST_CALLSIGN) and (len(msg.msg_str) != 0)): #don't retransmit if this request for acks is a broadcast
                    self.pending_acks[ack] = AckRetryObject(msg, DEFAULT_RETRY_CNT) #create a new entry in the dictionary
                self.pending_acks_lock.release()
                
            return self.writer.getFrameFromTextMessage(msg)
        elif (isinstance(msg,GPSMessageObject)):
            return self.writer.getFrameFromGPSMessage(msg)
    
    ##@brief check to see if there is a frame to transmit right now
    ##@return - Returns true when there is a frame to send, returns false otherwise
    def isTransmissionPending(self):
        if (self.msg_send_queue.empty() == False):
            return True
        elif (len(self.pending_acks) == 0):
            return False
        else:
            toReturn = False
            self.pending_acks_lock.acquire()
            for retry in self.pending_acks.values():
                if (retry.ready() == True):
                    toReturn = True
                    break
            self.pending_acks_lock.release()
            return toReturn
            
    ##@brief return the next Frame to be transmitted
    ##@return - Returns the next frame to be transmitted, prioritizing new frames, and then re-transmissions. Returns None if there is nothing to transmit
    def getNextFrameToTransmit(self):
        if (self.msg_send_queue.empty() == False):
            return self.msgToFrame(self.msg_send_queue.get())
        elif (len(self.pending_acks) == 0):
            return None
        else:
            toReturn = None
            self.pending_acks_lock.acquire()
            for key, retry in self.pending_acks.items():
                if (retry.ready() == True):
                    if (retry.ready() == True):
                        retry.decrement()
                        toReturn = self.writer.getFrameFromTextMessage(retry.msg)
                    else:
                        self.pending_acks.pop(key)
                        toReturn = self.getNextFrameToTransmit()   
            self.pending_acks_lock.release()
            return toReturn

    ##class used to read bytes from the phy layer and detect when a valid Frame is being received
    class IL2P_Frame_Reader:

        def __init__(self, verbose=False, frame_engine=frame_engine_default):
            self.src = None
            self.verbose = verbose
            
            self.state = 'IDLE'
            
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
                    self.state = 'IDLE'
                    log.info('raw frame received: 0x%s', raw_frame[0:ind].tobytes().hex())
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
        
        ##@brief get a string entered over the command line and put it inside an IL2P frame
        ##@return return the IL2P frame as an array of bytes
        def getInput(self):
            print(">", end ='') 
            input_str = input()
            
            header = IL2P_Frame_Header(src_callsign='BAYWAX',dst_callsign='WAYGAK',header_type=3,payload_byte_count=len(input_str))        
            frame = self.frame_engine.encode_frame(header, np.frombuffer(input_str.encode(),dtype=np.uint8))
            toReturn = frame.tobytes()
            if (self.verbose == True):
                log.info('raw frame to be sent: 0x%s', toReturn.hex())
            return toReturn
        
        ##@brief convert a simple text message to a frame ready to be sent
        ##@param msg a TextMessageObject to be converted into a frame
        def getFrameFromTextMessage(self, msg):
            ui_ack = 1 if (msg.expectAck==True) else 0
            header = IL2P_Frame_Header(src_callsign=msg.src_callsign,dst_callsign=msg.dst_callsign,header_type=3,payload_byte_count=len(msg.msg_str), ui=ui_ack, control=msg.seq_num)
            frame = self.frame_engine.encode_frame(header, np.frombuffer(msg.msg_str.encode(),dtype=np.uint8))
            toReturn = frame.tobytes()
            if (self.verbose == True):
                log.info('raw frame to be sent: 0x%s', toReturn.hex())
            return toReturn
            
        ##@brief convert a GPSMessageObject to a frame ready to be sent
        ##@param msg a GPSMessageObject to be converted into a frame
        def getFrameFromGPSMessage(self, msg):
            payload = str(msg.location).replace('\'','\"')
            header = IL2P_Frame_Header(src_callsign=msg.src_callsign, dst_callsign=BROADCAST_CALLSIGN, header_type=3, payload_byte_count=len(payload), ui=0, pid=GPS_PID, control=0)
            frame = self.frame_engine.encode_frame(header, np.frombuffer(payload.encode(), dtype=np.uint8))
            toReturn = frame.tobytes()
            if (self.verbose == True):
                log.info('raw frame to be sent: 0x%s', toReturn.hex())
            return toReturn
#if (b )
#if (b != 0):
#    print(b.to_bytes(1,'big'))                


