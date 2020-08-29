import numpy as np
import io
import time
#import threading
import queue
import view

from IL2P import *

log = logging.getLogger(__name__)

#IL2P constants

RAW_FRAME_MAXLEN = 1299 #the length in bytes of a raw IL2P header before removing error correction symbols and including the header and sync byte
RAW_HEADER_LEN = 25 #the length of an IL2P header in bytes before removing its error correction symbols
PREAMBLE_LEN = 1

frame_engine_default = IL2P_Frame_Engine()

##class used to read bytes from the phy layer and detect when a valid Frame is being received
class IL2P_Frame_Reader:

    ##@param msg_output_queue the queue to send decoded messages to
    def __init__(self, verbose=False, frame_engine=frame_engine_default, msg_output_queue = None):
        self.src = None
        self.verbose = verbose
        self.msg_output_queue = msg_output_queue
        
        self.state = 'IDLE'
        
        self.frame_engine = frame_engine
    
    ##@brief sets the data source to be used by the IL2P_Frame_Reader and starts the frame reading thread
    ##@param src a ReceiverPipe object that will be filled with decoded bytes by the phy layer
    def setSource(self, src):
        self.src = src
    
    ##@brief function to be called when the phy layer has a full frame ready for the link layer
    ##@return returns true when the frame is decoded correctly, returns false otherwise
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
                    
                    src = header.src_callsign
                    dst = header.dst_callsign
                    ack = True if (header.ui == 1) else False
                    seq = header.control
                    msg = payload_bytes.tobytes().decode('ascii','ignore') #convert payload bytes to a string while ignoring all non-ascii characters
                    
                    txt_msg = view.view_controller.TextMessageObject(msg, src, dst, ack, seq)
                    self.msg_output_queue.put(txt_msg)
                    
                except exceptions.IL2PHeaderDecodeError:
                    log.warning('Failed to decode a frame header, the rest of the frame will be discarded')
                    return False
                except BaseException:
                    log.warning('Failed to decode frame')
                    return False
                break
        return True

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
    
    
    #convert a simple text message to a frame ready to be sent
    def getFrameFromTextMessage(self, msg_str, src, dst, ack, seq):
        ui_ack = 1 if (ack==True) else 0
        header = IL2P_Frame_Header(src_callsign=src,dst_callsign=dst,header_type=3,payload_byte_count=len(msg_str), ui=ui_ack, control=seq)
        frame = self.frame_engine.encode_frame(header, np.frombuffer(msg_str.encode(),dtype=np.uint8))
        toReturn = frame.tobytes()
        if (self.verbose == True):
            log.info('raw frame to be sent: 0x%s', toReturn.hex())
        return toReturn
#if (b )
#if (b != 0):
#    print(b.to_bytes(1,'big'))                


