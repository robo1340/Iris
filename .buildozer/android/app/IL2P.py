import numpy as np
import io
import time
import threading
import queue
import logging

import interleaving
from fec.fec import *
from interleaving.Interleaver import *
import exceptions        

log = logging.getLogger(__name__)

preamble = np.array([0x55],dtype=np.uint8)

##A class used to prepare IL2P data for transmission and decode received IL2P frames
class IL2P_Frame_Engine:

    ##@brief constructor for the IL2P_Frame_Engine class
    def __init__(self):
        
        self.header_codec = FrameHeaderCodec() #the solomon read encoder/decoder object
        self.payload_encoder = FramePayloadEncoder() #the solomon read encoder object for frame payloads
        self.payload_decoder = FramePayloadDecoder()
        self.interleaver = Interleaver()
        self.deinterleaver = Deinterleaver()
    
    ##@brief prepares frame for modulation by packing header information into 13 bytes and interleaving the bits
    ##@param header_bytes 1d numpy array of length 13 holding the IL2P header information
    ##@param frame_payload_bytes, the payload bytes to be interleaved right after the frame header
    ##@return a tuple of 1d numpy arrays, the first contains the interleaved header, the second the interleaved frame_payload_bytes
    def __apply_interleaving(self,header_bytes,frame_payload_bytes):

        frame_bytes = np.concatenate( (header_bytes,frame_payload_bytes) )
        
        self.interleaver.reset()
        interleaved_frame_bytes = self.interleaver.scramble_bits(frame_bytes)
        
        return (interleaved_frame_bytes[0:13], interleaved_frame_bytes[13:,])
    
    ##@brief method used to prepare frames for modulation
    ##@param header a IL2P_Frame_Header object containing the header information
    ##@param payload_bytes a 1d numpy array of bytes holding the frame payload information
    ##@return returns a 1d numpy array of bytes holding the data ready to be modulated over the radio interface
    def encode_frame(self,header,payload_bytes):
    
        (interleaved_header, interleaved_payload) = self.__apply_interleaving(header.pack_header(), payload_bytes)
        fec_encoded_header = self.header_codec.encode(interleaved_header)
        fec_encoded_payload = self.payload_encoder.encode(interleaved_payload)
        
        return np.concatenate( (preamble,fec_encoded_header,fec_encoded_payload) )
    
    ##@brief extract the header and payload information from a newly received frame
    ##@param raw_frame the raw frame bytes that were received
    ##@throws IL2PHeaderDecodeError thrown when the Solomon Reed decoder could not correct all the errors in the frame header
    ##@return returns a tuple. The first element is an IL2P_Frame_Header object, the second is a boolean that is true if the full payload could be corrected, the third is the frame payload information as a numpy 1d array of bytes
    def decode_frame(self, raw_frame):
        if (len(raw_frame) < 26):
            raise ValueError('raw_frame is to short to be an IL2P frame')
        if (raw_frame[0] != preamble[0]):
            log.warning('WARNING: link layer preamble is incorrect')
        (decode_success,header_decoded) = self.header_codec.decode(raw_frame[1:26])
        
        if (decode_success == False): #if the header could not be decoded
            raise exceptions.IL2PHeaderDecodeError('Error: could not decode the IL2P frame header')
            return
        
        self.deinterleaver.reset() #reset the deinterleaver LFSR
        header_bytes = self.deinterleaver.descramble_bits(header_decoded)
        header = IL2P_Frame_Header.unpack_header(header_bytes)

        (payload_decode_success, payload_decoded) = self.payload_decoder.decode(raw_frame[26:,], header.getPayloadSize())

        payload_bytes = self.deinterleaver.descramble_bits(payload_decoded)

        return (header, payload_decode_success, payload_bytes)
        
    ##@brief extract the header information from a newly received frame, this function may be called before the payload has been fully received
    ##@param raw_header the raw frame bytes that were received, including the preamble byte
    ##@throws IL2PHeaderDecodeError thrown when the Solomon Reed decoder could not correct all errors in the frame header
    ##@throws valueError, thrown when the arguments passed in are not correct
    ##@return returns an IL2P_Frame_Header object
    def decode_header(self, raw_header, verbose=True):
        if (len(raw_header) < 26):
            raise ValueError('raw_header is to short to be an IL2P header')
        if (raw_header[0] != preamble[0]):
            log.warning('WARNING: link layer preamble is incorrect')
        (decode_success,header_decoded) = self.header_codec.decode(raw_header[1:26],verbose)
        
        if (decode_success == False): #if the header could not be decoded
            raise exceptions.IL2PHeaderDecodeError('Error: could not decode the IL2P frame header')
            return
        
        self.deinterleaver.reset() #reset the deinterleaver LFSR
        header_bytes = self.deinterleaver.descramble_bits(header_decoded)
        header = IL2P_Frame_Header.unpack_header(header_bytes)

        return header
        
        
##A class representing an IL2P frame header and all its attributes
class IL2P_Frame_Header:

    SSID_MASK           = np.uint8(0x0f)
    UI_MASK             = np.uint8(0x01)
    PID_MASK            = np.uint8(0x0F) 
    CONTROL_MASK        = np.uint8(0x7F) 
    HEADER_TYPE_MASK    = np.uint8(0x03)
    PAYLOAD_COUNT_MASK  = np.uint16(0x03FF) 

    ##@brief constructor for the IL2P_Frame class. Params for constructor include all the info needed to form a 13 byte header
    ##@param src_callsign the source callsign for this frame, a 6 character string
    ##@param dst_callsign the destination callsign for this frame, a 6 character string
    ##@param src_ssid the source ssid for this frame, a 4 bit field
    ##@param dst_ssid the destination ssid for this frame, a 4 bit field
    ##@param ui a 1 bit field
    ##@param pid a 4 bit field
    ##@param control a 7 bit field
    ##@param header_type a 2 bit field
    ##@param payload_byte_count a 10 bit field indicating how many bytes of information is in the payload for this frame
    def __init__(self, src_callsign='GAYWAX',dst_callsign='BAYWAX',src_ssid=0,dst_ssid=0,ui=0,pid=0,control=0,header_type=2,payload_byte_count=0):
        self.src_callsign       = src_callsign
        self.dst_callsign       = dst_callsign
        self.src_ssid           = np.uint8(src_ssid)            & self.SSID_MASK
        self.dst_ssid           = np.uint8(dst_ssid)            & self.SSID_MASK
        self.ui                 = np.uint8(ui)                  & self.UI_MASK
        self.pid                = np.uint8(pid)                 & self.PID_MASK
        self.control            = np.uint8(control)             & self.CONTROL_MASK
        self.header_type        = np.uint8(header_type)         & self.HEADER_TYPE_MASK
        self.payload_byte_count = np.uint16(payload_byte_count) & self.PAYLOAD_COUNT_MASK
    
    def getPayloadSize(self):
        return int(self.payload_byte_count)
        
    def setPayloadSize(self, new_count):
        self.payload_byte_count = np.uint16(new_count)  & self.PAYLOAD_COUNT_MASK
        
    ##@brief calculate the raw payload length from the payload length given in the frame header's 10 bit field
    ##@param payload_len the payload length given in the frame header's 10 bit field.
    def getRawPayloadSize(self):
        if (self.payload_byte_count <= 0):
            return 0
        block_cnt = ceil(self.payload_byte_count/205) #the number of blocks (up to 255 bytes each) to break msg into
        small_block_len = floor(self.payload_byte_count/block_cnt) #the length (in bytes) of a small block
        large_block_len = small_block_len + 1 #the length (in bytes) of a large block
        large_block_cnt = self.payload_byte_count - (block_cnt*small_block_len) #the number of large blocks that will be used
        small_block_cnt = block_cnt - large_block_cnt #the number of small blocks that will be used
        ecc_sym_cnt = floor(small_block_len/5) + 10 #the number of error correction symbols that will be appended to each block
        return ((small_block_cnt*(small_block_len+ecc_sym_cnt)) + (large_block_cnt*(large_block_len+ecc_sym_cnt)))
    
    ##@brief packs the header information into 13 bytes.
    ##@return returns a 1d numpy array of 13 bytes
    def pack_header(self):
        toReturn = np.zeros((13),dtype=np.uint8)
        
        ind = 0
        #pack the destination callsign bytes
        for char in self.dst_callsign:
            b = np.frombuffer(char.encode(),dtype=np.uint8) #convert the character to a byte
            toReturn[ind] = (b-np.uint8(0x20)) & np.uint8(0x3F) #get the sixbit representation of the character and store it to the lower six bits of one of toReturn's bytes
            ind += 1
            
        #pack the source callsign bytes
        for char in self.src_callsign:
            b = np.frombuffer(char.encode(),dtype=np.uint8) #convert the character to a byte
            toReturn[ind] = (b-np.uint8(0x20)) & np.uint8(0x3F) #get the sixbit representation of the character and store it to the lower six bits of one of toReturn's bytes
            ind += 1
            
        #set the UI bit
        toReturn[0] |= (self.ui & np.uint8(0x01)) << 6
        
        #set the PID bits
        toReturn[1] |= ((self.pid >> 3) & np.uint8(0x01)) << 6
        toReturn[2] |= ((self.pid >> 2) & np.uint8(0x01)) << 6
        toReturn[3] |= ((self.pid >> 1) & np.uint8(0x01)) << 6
        toReturn[4] |= (self.pid & np.uint8(0x01)) << 6
        
        #set the control bits
        toReturn[5] |= ((self.control >> 6) & np.uint8(0x01)) << 6
        toReturn[6] |= ((self.control >> 5) & np.uint8(0x01)) << 6
        toReturn[7] |= ((self.control >> 4) & np.uint8(0x01)) << 6
        toReturn[8] |= ((self.control >> 3) & np.uint8(0x01)) << 6
        toReturn[9] |= ((self.control >> 2) & np.uint8(0x01)) << 6
        toReturn[10]|= ((self.control >> 1) & np.uint8(0x01)) << 6
        toReturn[11]|= (self.control & np.uint8(0x01)) << 6
        
        #set the header type bits
        toReturn[0] |= ((self.header_type >> 1) & np.uint8(0x01)) << 7
        toReturn[1] |= ((self.header_type)      & np.uint8(0x01)) << 7
        
        #set the payload byte count bits
        toReturn[2] |= ((self.payload_byte_count >> 9) & np.uint8(0x01)) << 7
        toReturn[3] |= ((self.payload_byte_count >> 8) & np.uint8(0x01)) << 7
        toReturn[4] |= ((self.payload_byte_count >> 7) & np.uint8(0x01)) << 7
        toReturn[5] |= ((self.payload_byte_count >> 6) & np.uint8(0x01)) << 7
        toReturn[6] |= ((self.payload_byte_count >> 5) & np.uint8(0x01)) << 7
        toReturn[7] |= ((self.payload_byte_count >> 4) & np.uint8(0x01)) << 7
        toReturn[8] |= ((self.payload_byte_count >> 3) & np.uint8(0x01)) << 7
        toReturn[9] |= ((self.payload_byte_count >> 2) & np.uint8(0x01)) << 7
        toReturn[10]|= ((self.payload_byte_count >> 1) & np.uint8(0x01)) << 7
        toReturn[11]|= (self.payload_byte_count & np.uint8(0x01)) << 7
        
        #set the SSID byte
        toReturn[12] = ((self.dst_ssid & np.uint8(0x0F))<<4) | (self.src_ssid & np.uint8(0x0F))
        
        return toReturn
    
    def getInfoString(self):
        fmt = 'SRC Callsign: {0:s}, DST Callsign: {1:s}, src ssid: 0x{2:s}, dst ssid: 0x{3:s}, ui:0x{4:s}, pid:0x{5:s}, ctrl:0x{6:s}, type:0x{7:s}, payload length:{8:d}'
        return fmt.format(self.src_callsign, self.dst_callsign, 
          self.src_ssid.tobytes().hex(), self.dst_ssid.tobytes().hex(),
          self.ui.tobytes().hex(), self.pid.tobytes().hex(), self.control.tobytes().hex(), 
          self.header_type.tobytes().hex(), self.payload_byte_count )
    
    def print(self):
        print(self.getInfoString())
    
    ##@brief compares the contents of two headers and returns true when they are the same
    ##@param the IL2P_Frame_Header object to compare to self
    ##@return returns true when self and header have the same field values, returns false otherwise
    def equals(self,header):
        if not((header.src_callsign == self.src_callsign) and (header.dst_callsign == self.dst_callsign)):
            return False
        if not((header.src_ssid == self.src_ssid) and (header.dst_ssid == self.dst_ssid)):
            return False
        if not((header.ui == self.ui)and(header.pid == self.pid)and(header.control == self.control)and(header.header_type == self.header_type)and(header.payload_byte_count == self.payload_byte_count)):
            return False
            
        return True
        
    ##@brief unpacks header information that was stored in a 13 bytes array and returns a new IL2P_Frame_Header object
    ##@param header_bytes numpy 1d array of bytes of length 13 holding the IL2P header information
    ##@return returns an IL2P_Frame_Header object
    def unpack_header(header_bytes):
        src_cs = np.zeros((6), dtype=np.uint8)
        dst_cs = np.zeros((6), dtype=np.uint8)
        
        for i in range(0,6):
            dst_cs[i] = (header_bytes[i]    & np.uint8(0x3F)) + np.uint8(0x20)
            src_cs[i] = (header_bytes[i+6]  & np.uint8(0x3F)) + np.uint8(0x20)
            
        ui = (header_bytes[0] >> 6) & np.uint8(0x01)
        
        pid = np.uint8(0x00)
        pid |= ((header_bytes[1] >> 6) & np.uint8(0x01)) << 3
        pid |= ((header_bytes[2] >> 6) & np.uint8(0x01)) << 2
        pid |= ((header_bytes[3] >> 6) & np.uint8(0x01)) << 1
        pid |= ((header_bytes[4] >> 6) & np.uint8(0x01))
        
        control = np.uint8(0x00)
        control |= ((header_bytes[5] >> 6) & np.uint8(0x01)) << 6
        control |= ((header_bytes[6] >> 6) & np.uint8(0x01)) << 5
        control |= ((header_bytes[7] >> 6) & np.uint8(0x01)) << 4
        control |= ((header_bytes[8] >> 6) & np.uint8(0x01)) << 3
        control |= ((header_bytes[9] >> 6) & np.uint8(0x01)) << 2
        control |= ((header_bytes[10]>> 6) & np.uint8(0x01)) << 1
        control |= ((header_bytes[11]>> 6) & np.uint8(0x01))
        
        type = np.uint8(0x00)
        type |= ((header_bytes[0] >> 7) & np.uint8(0x01)) << 1
        type |= ((header_bytes[1] >> 7) & np.uint8(0x01))
        
        count = np.uint16(0x0000)
        count |= np.uint16(((header_bytes[2] >> 7) & np.uint16(0x0001))) << 9
        count |= np.uint16(((header_bytes[3] >> 7) & np.uint16(0x0001))) << 8
        count |= np.uint16(((header_bytes[4] >> 7) & np.uint16(0x0001))) << 7
        count |= np.uint16(((header_bytes[5] >> 7) & np.uint16(0x0001))) << 6
        count |= np.uint16(((header_bytes[6] >> 7) & np.uint16(0x0001))) << 5
        count |= np.uint16(((header_bytes[7] >> 7) & np.uint16(0x0001))) << 4
        count |= np.uint16(((header_bytes[8] >> 7) & np.uint16(0x0001))) << 3
        count |= np.uint16(((header_bytes[9] >> 7) & np.uint16(0x0001))) << 2
        count |= np.uint16(((header_bytes[10]>> 7) & np.uint16(0x0001))) << 1
        count |= np.uint16(((header_bytes[11]>> 7) & np.uint16(0x0001)))
        
        src_id = header_bytes[12]           & np.uint8(0x0F)
        dst_id = (header_bytes[12] >> 4)    & np.uint8(0x0F)
        
        return IL2P_Frame_Header(src_callsign=src_cs.tobytes().decode(),dst_callsign=dst_cs.tobytes().decode(),src_ssid=src_id,dst_ssid=dst_id,ui=ui,pid=pid,control=control,header_type=type,payload_byte_count=count)
        





