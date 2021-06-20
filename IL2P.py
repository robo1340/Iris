import numpy as np
import io
import time
import threading
import queue

import interleaving
from fec.fec import *
from interleaving.Interleaver import *
import exceptions        

from kivy.logger import Logger as log

IL2P_HDR_LEN = 32
IL2P_HDR_LEN_ENC = 64

##A class used to prepare IL2P data for transmission and decode received IL2P frames
class IL2P_Frame_Engine:

    ##@brief constructor for the IL2P_Frame_Engine class
    def __init__(self):
        
        self.header_codec = FrameHeaderCodec() #the solomon read encoder/decoder object
        self.payload_encoder = FramePayloadEncoder() #the solomon read encoder object for frame payloads
        self.payload_decoder = FramePayloadDecoder()
        self.interleaver = Interleaver()
        self.deinterleaver = Deinterleaver()
        self.f = lambda i, n, k : (i*k)%n #byte scrambling function
     
    ##@brief prepares frame for modulation by packing header information into 32 bytes and interleaving the bits
    ##@param header_bytes 1d numpy array of length 32 holding the IL2P header information
    ##@param frame_payload_bytes, the payload bytes to be interleaved right after the frame header
    ##@return a tuple of 1d numpy arrays, the first contains the interleaved header, the second the interleaved frame_payload_bytes
    def __apply_interleaving(self,header_bytes,frame_payload_bytes):

        frame_bytes = np.concatenate( (header_bytes,frame_payload_bytes) )
        self.interleaver.reset()
        interleaved_frame_bytes = self.interleaver.scramble_bits(frame_bytes)
        return (interleaved_frame_bytes[0:32], interleaved_frame_bytes[32:,])
    
    ##@brief method used to prepare frames for modulation
    ##@param header a IL2P_Frame_Header object containing the header information
    ##@param payload_bytes a 1d numpy array of bytes holding the frame payload information
    ##@return returns a 1d numpy array of bytes holding the data ready to be modulated over the radio interface
    def encode_frame(self,header,payload_bytes):
        (interleaved_header, interleaved_payload) = self.__apply_interleaving(header.pack_header(), payload_bytes)
        fec_encoded_header = self.header_codec.encode(interleaved_header)
        fec_encoded_payload = self.payload_encoder.encode(interleaved_payload)
        
        return np.concatenate( (fec_encoded_header,fec_encoded_payload) )
    
    ##@brief extract the header and payload information from a newly received frame
    ##@param raw_frame the raw frame bytes that were received
    ##@throws IL2PHeaderDecodeError thrown when the Solomon Reed decoder could not correct all the errors in the frame header
    ##@return returns a tuple. The first element is an IL2P_Frame_Header object, the second is a boolean that is true if the full payload could be corrected, the third is the frame payload information as a numpy 1d array of bytes
    def decode_frame(self, raw_frame):
        if (len(raw_frame) < 64):
            raise ValueError('raw_frame is to short to be an IL2P frame')

        (decode_success,header_decoded) = self.header_codec.decode(raw_frame[0:64])
        
        if (decode_success == False): #if the header could not be decoded
            raise exceptions.IL2PHeaderDecodeError('Error: could not decode the IL2P frame header')
            return
        
        self.deinterleaver.reset() #reset the deinterleaver LFSR
        header_bytes = self.deinterleaver.descramble_bits(header_decoded)
        header = IL2P_Frame_Header.unpack_header(header_bytes)

        (payload_decode_success, payload_decoded) = self.payload_decoder.decode(raw_frame[64:,], header.getPayloadSize())

        payload_bytes = self.deinterleaver.descramble_bits(payload_decoded)

        return (header, payload_decode_success, payload_bytes)
        
    ##@brief extract the header information from a newly received frame, this function may be called before the payload has been fully received
    ##@param raw_header the raw frame bytes that were received, including the preamble byte
    ##@throws IL2PHeaderDecodeError thrown when the Solomon Reed decoder could not correct all errors in the frame header
    ##@throws valueError, thrown when the arguments passed in are not correct
    ##@return returns an IL2P_Frame_Header object
    def decode_header(self, raw_header, verbose=True):
        if (len(raw_header) < 64):
            print(len(raw_header))
            raise ValueError('raw_header is to short to be an IL2P header')
        (decode_success,header_decoded) = self.header_codec.decode(raw_header[0:64],verbose)
         
        if (decode_success == False): #if the header could not be decoded
            raise exceptions.IL2PHeaderDecodeError('Error: could not decode the IL2P frame header')
            return
        
        self.deinterleaver.reset() #reset the deinterleaver LFSR
        header_bytes = self.deinterleaver.descramble_bits(header_decoded)
        header = IL2P_Frame_Header.unpack_header(header_bytes)

        return header
        
##A class representing an IL2P frame header and all its attributes
class IL2P_Frame_Header:

    ##@brief constructor for the IL2P_Frame class. Params for constructor include all the info needed to form a 13 byte header
    ##@param src_callsign the source callsign for this frame, a 6 character string
    ##@param link_src_callsign the source of the frame for multihop transmissions
    ##@param my_seq when request ack is true contains my ack's sequence number, when false contains most recent acknowledgement
    ##@param dst_callsign the destination callsign for this frame, a 6 character string
    def __init__(self, src_callsign='GAYWAX', link_src_callsign=None, dst_callsign='BAYWAX', \
               hops_remaining=1, hops=1, is_text_msg=True, is_beacon=False, \
               my_seq = np.uint16(0), \
               acks=[False,False,False,False], \
               request_ack=True, request_double_ack=False, \
               payload_size=0, data=np.zeros((4),dtype=np.uint16)):
        self.src_callsign = src_callsign.ljust(6,' ')[0:6]
        self.link_src_callsign = self.src_callsign if (link_src_callsign is None) else link_src_callsign.ljust(6,' ')[0:6]
        self.dst_callsign = dst_callsign.ljust(6,' ')[0:6]
        self.hops = hops
        self.hops_remaining = hops_remaining
        self.is_text_msg = is_text_msg
        self.is_beacon = is_beacon
        self.acks = acks
        self.request_ack = request_ack
        self.request_double_ack = request_double_ack
        self.payload_size = np.uint16(payload_size)
        self.my_seq = np.uint16(my_seq)
        self.data = data
    
    def getPayloadSize(self):
        return self.payload_size
        
    def setPayloadSize(self, new_count):
        self.payload_size = np.uint16(new_count)
        
    ##@brief calculate the raw payload length from the payload length given in the frame header's 10 bit field
    ##@param payload_len the payload length given in the frame header's 10 bit field.
    def getRawPayloadSize(self):
        if (self.payload_size <= 0):
            return 0
        block_cnt = ceil(self.payload_size/205) #the number of blocks (up to 255 bytes each) to break msg into
        small_block_len = floor(self.payload_size/block_cnt) #the length (in bytes) of a small block
        large_block_len = small_block_len + 1 #the length (in bytes) of a large block
        large_block_cnt = self.payload_size - (block_cnt*small_block_len) #the number of large blocks that will be used
        small_block_cnt = block_cnt - large_block_cnt #the number of small blocks that will be used
        ecc_sym_cnt = floor(small_block_len/5) + 10 #the number of error correction symbols that will be appended to each block
        return ((small_block_cnt*(small_block_len+ecc_sym_cnt)) + (large_block_cnt*(large_block_len+ecc_sym_cnt)))
    
    ##@brief packs the header information into 32 bytes.
    ##@return returns a 1d numpy array of 32 bytes
    def pack_header(self):
        toReturn = np.zeros((32),dtype=np.uint8)
        i=0
        
        dst = self.dst_callsign.encode()
        toReturn[i]   = np.uint8(dst[0])
        toReturn[i+1] = np.uint8(dst[1])
        toReturn[i+2] = np.uint8(dst[2])
        toReturn[i+3] = np.uint8(dst[3])
        toReturn[i+4] = np.uint8(dst[4])
        toReturn[i+5] = np.uint8(dst[5])
        i=i+6
        
        lnk = self.link_src_callsign.encode()
        toReturn[i]   = np.uint8(lnk[0])
        toReturn[i+1] = np.uint8(lnk[1])
        toReturn[i+2] = np.uint8(lnk[2])
        toReturn[i+3] = np.uint8(lnk[3])
        toReturn[i+4] = np.uint8(lnk[4])
        toReturn[i+5] = np.uint8(lnk[5])
        i=i+6
        
        src = self.src_callsign.encode()
        toReturn[i]   = np.uint8(src[0])
        toReturn[i+1] = np.uint8(src[1])
        toReturn[i+2] = np.uint8(src[2])
        toReturn[i+3] = np.uint8(src[3])
        toReturn[i+4] = np.uint8(src[4])
        toReturn[i+5] = np.uint8(src[5])
        i=i+6
        
        #set the flag bits
        toReturn[i] |= np.uint8(0x80) if (self.request_double_ack) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x40) if (self.request_ack) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x20) if (self.acks[3]) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x10) if (self.acks[2]) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x08) if (self.acks[1]) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x04) if (self.acks[0]) else np.uint8(0x00)
        i=i+1
        
        toReturn[i] |= np.uint8(0x20) if (self.hops >= 2) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x10) if ((self.hops >= 1) and (self.hops != 2)) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x08) if (self.is_beacon) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x04) if (self.is_text_msg) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x02) if (self.hops_remaining >= 2) else np.uint8(0x00)
        toReturn[i] |= np.uint8(0x01) if ((self.hops_remaining >= 1) and (self.hops_remaining != 2)) else np.uint8(0x00)
        i=i+1
        
        ph = np.uint8(np.uint16(self.payload_size) >> 8)
        pl = np.uint8(self.payload_size & np.uint8(0xFF) )
        toReturn[i]   = ph
        toReturn[i+1] = pl
        i=i+2
        
        mh = np.uint8(np.uint16(self.my_seq) >> 8)
        ml = np.uint8(self.my_seq & np.uint8(0xFF) )
        toReturn[i]   = mh
        toReturn[i+1] = ml
        i=i+2
        
        d0h = np.uint8(np.uint16(self.data[0]) >> 8)
        d0l = np.uint8(np.uint16(self.data[0]) & np.uint8(0xFF))
        toReturn[i]   = d0h
        toReturn[i+1] = d0l
        i=i+2
        
        d1h = np.uint8(np.uint16(self.data[1]) >> 8)
        d1l = np.uint8(np.uint16(self.data[1]) & np.uint8(0xFF))
        toReturn[i]   = d1h
        toReturn[i+1] = d1l
        i=i+2
        
        d2h = np.uint8(np.uint16(self.data[2]) >> 8)
        d2l = np.uint8(np.uint16(self.data[2]) & np.uint8(0xFF))
        toReturn[i]   = d2h
        toReturn[i+1] = d2l
        i=i+2
        
        d3h = np.uint8(np.uint16(self.data[3]) >> 8)
        d3l = np.uint8(np.uint16(self.data[3]) & np.uint8(0xFF))
        toReturn[i] = d3h
        toReturn[i+1] = d3l
        i=i+2
        
        return toReturn
        
    def print_header(self):
        log.info("src %s dst %s hops %d hopsr %d" % (self.src_callsign, self.dst_callsign, self.hops, self.hops_remaining))
        log.info("is text %s is beacon %s" % (str(self.is_text_msg), str(self.is_beacon)))
        log.info("acks bool %s acks data %s" % (str(self.acks), str(self.data)))
        log.info("requests ack %s requests double ack %s" % (str(self.request_ack), str(self.request_double_ack)))
        log.info("payload size %d" % (self.payload_size))
        print('-------------------')
    
    ##@brief compares the contents of two headers and returns true when they are the same
    ##@param the IL2P_Frame_Header object to compare to self
    ##@return returns true when self and header have the same field values, returns false otherwise
    def equals(self,header):
        if not((header.src_callsign == self.src_callsign) and (header.dst_callsign == self.dst_callsign)):
            return False
        if not (header.hops_remaining == self.hops_remaining):
            return False
        if not ((header.hops == self.hops) and (header.is_text_msg == self.is_text_msg) and (header.is_beacon == self.is_beacon)):
            return False
        if not (header.acks == self.acks):
            return False
        if not ((header.request_ack == self.request_ack) and (header.request_double_ack == self.request_double_ack)):
            return False
        if not ((header.payload_size == self.payload_size) and (header.data[0] == self.data[0])):
            return False
        if not ((header.data[1] == self.data[1]) and (header.data[2] == self.data[2]) and (header.data[3] == self.data[3])):
            return False
        return True
    
    def getForwardAckSequenceList(self):
        to_return = []
        for ind, ack in enumerate(self.acks):
            if (ack):
                to_return.append(self.data[ind])
        if ((not self.request_ack) and (not self.request_double_ack) and (self.my_seq != 0)):
            to_return.append(self.my_seq)
        log.info(to_return)
        return to_return
    
    def getMyAckSequence(self):
        return self.my_seq
    
    ##@brief unpacks header information that was stored in a 32 bytes array and returns a new IL2P_Frame_Header object
    ##@param header_bytes numpy 1d array of bytes of length 32 holding the IL2P header information
    ##@return returns an IL2P_Frame_Header object
    def unpack_header(header_bytes):
        src_cs = np.zeros((6), dtype=np.uint8)
        lnk_cs = np.zeros((6), dtype=np.uint8)
        dst_cs = np.zeros((6), dtype=np.uint8)
        
        for i in range(0,6):
            dst_cs[i] = (header_bytes[i])
            lnk_cs[i] = (header_bytes[i+6])
            src_cs[i] = (header_bytes[i+12])
        ack = [False,False,False,False]
        request_double_ack = True if (header_bytes[18] & np.uint(0x80)) != 0 else False
        request_ack        = True if (header_bytes[18] & np.uint(0x40)) != 0 else False
        ack[3]             = True if (header_bytes[18] & np.uint(0x20)) != 0 else False
        ack[2]             = True if (header_bytes[18] & np.uint(0x10)) != 0 else False
        ack[1]             = True if (header_bytes[18] & np.uint(0x08)) != 0 else False
        ack[0]             = True if (header_bytes[18] & np.uint(0x04)) != 0 else False
        
        hops               = (header_bytes[19] >>4) & np.uint8(0x03)
        is_beacon          = True if (header_bytes[19] & np.uint(0x08)) != 0 else False
        is_text_msg        = True if (header_bytes[19] & np.uint(0x04)) != 0 else False                                                
        hops_remaining     = header_bytes[19] & np.uint8(0x03)
        
        payload_size = np.uint16( (np.uint16(header_bytes[20])<<8) | np.uint16(header_bytes[21]) )
        my_seq       = np.uint16( (np.uint16(header_bytes[22])<<8) | np.uint16(header_bytes[23]) )
        data = np.zeros((4),dtype=np.uint16)
        data[0] = np.uint16( (np.uint16(header_bytes[24])<<8) | np.uint16(header_bytes[25]) )
        data[1] = np.uint16( (np.uint16(header_bytes[26])<<8) | np.uint16(header_bytes[26]) )
        data[2] = np.uint16( (np.uint16(header_bytes[28])<<8) | np.uint16(header_bytes[29]) )
        data[3] = np.uint16( (np.uint16(header_bytes[30])<<8) | np.uint16(header_bytes[31]) )
        
        return IL2P_Frame_Header(src_callsign = src_cs.tobytes().decode(), \
                                 link_src_callsign = lnk_cs.tobytes().decode(), \
                                 dst_callsign = dst_cs.tobytes().decode(), \
                                 hops_remaining=hops_remaining, hops=hops, \
                                 is_text_msg=is_text_msg, is_beacon=is_beacon, \
                                 acks=ack, my_seq = my_seq, \
                                 request_ack=request_ack, request_double_ack=request_double_ack, \
                                 payload_size=payload_size, data=data)


