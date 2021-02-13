import numpy as np
from math import floor,ceil

from fec.reedsolo import *

from kivy.logger import Logger as log

##class used to handle Reed Solomon encoding/decoding of IL2P frame headers
class FrameHeaderCodec:
    
    def __init__(self):
        self.rsc = RSCodec(12) #the Reed Solomon encoder/decoder object

    ##@brief Perform Reed Solomon encoding to form a 25 byte IL2P header
    ##@param A numpy 1d array of bytes holding the header_msg the 13 byte header data message after interleaving, but before RS encoding
    ##@return A numpy 1d array of bytes holding the 25 byte IL2P header with ecc symbols appended
    def encode(self,header_msg):
        assert (header_msg.size == 13)
        #if (header_msg.size != 13):
        #    raise Exception("header message is not the correct length, expected length is 13 bytes")
    
        toReturn = np.frombuffer(self.rsc.encode(header_msg), dtype=np.uint8)
        return toReturn
    
    ##@brief Perform Reed Solomon decoding to extract a 13 byte IL2P header
    ##@param header A numpy 1d array of bytes holding the 25 byte received header
    ##@return A tuple. The first element is true when decoding was successful. The second element is a numpy 1d array of bytes holding the 13 byte IL2P header
    def decode(self,header,verbose=True):
        assert (header.size == 25)
        #if (header.size != 25):
        #    raise Exception("header message is not the correct length, expected length is 25 bytes")
        
        toReturn = np.zeros((13), dtype=np.uint8)
        decodeSuccess = True
        
        try:
            decoded, _ , error_ind = self.rsc.decode(header)
            toReturn = np.frombuffer(decoded, dtype=np.uint8)
            if (verbose):
                log.info('\thdr, %d err', len(error_ind))
        except ReedSolomonError:
            log.warning('\tWarning: Header decoding failed!')
            decodeSuccess = False
            
        return (decodeSuccess, toReturn)

##class used to handle Reed Solmon encoding of IL2P frame payloads
class FramePayloadEncoder:

    def __init__(self):
        self.ecc_sym_cnt = 50
        self.rsc = RSCodec(self.ecc_sym_cnt)  # the Reed Solomon encoder/decoder object
    
    ##append RS characters to a numpy byte array, msg
    ##return a matrix of bytes, where each row is chunk with its RS characters appended
    
    ##@brief Perform Solomon Reed encoding to form an IL2P frame payload
    ##@param msg A numpy 1-dimensional array of bytes to be encoded
    ##@return A numpy 1-dimensional array of bytes with error correction symbols appended
    def encode(self,msg):
        if (len(msg) == 0):
            return np.empty((0,0), dtype=np.uint8).flatten('C')
        
        block_cnt = ceil(len(msg)/205) #the number of blocks (up to 255 bytes each) to break msg into
        small_block_len = floor(len(msg)/block_cnt) #the length (in bytes) of a small block
        large_block_len = small_block_len + 1 #the length (in bytes) of a large block
        large_block_cnt = len(msg) - (block_cnt*small_block_len) #the number of large blocks that will be used
        small_block_cnt = block_cnt - large_block_cnt #the number of small blocks that will be used
        
        ecc_sym_cnt = floor(small_block_len/5) + 10 #the number of error correction symbols that will be appended to each block
        
        if (ecc_sym_cnt != self.ecc_sym_cnt):
            self.ecc_sym_cnt = ecc_sym_cnt
            self.rsc = RSCodec(ecc_sym_cnt)
        
        large_blocks = np.zeros((large_block_cnt, large_block_len+ecc_sym_cnt), dtype=np.uint8) #matrix of bytes where each row is large block of data
        small_blocks = np.zeros((small_block_cnt, small_block_len+ecc_sym_cnt), dtype=np.uint8) #matrix of bytes where each row is a small block of data
        
        msg_ind = 0 #the current indice of msg we are encoding
        
        #encode the large blocks from msg
        for i in range(0,large_block_cnt):
            large_blocks[i,:] = np.frombuffer(self.rsc.encode(msg[msg_ind:msg_ind+large_block_len]), dtype=np.uint8)
            msg_ind += large_block_len
        
        #encode the small blocks from msg
        for i in range(0,small_block_cnt):
            sub_arr = msg[msg_ind:msg_ind+small_block_len].tobytes()
            small_blocks[i,:] = np.frombuffer(self.rsc.encode(sub_arr), dtype=np.uint8)
            msg_ind += small_block_len
        
        toReturn = np.concatenate( (large_blocks.flatten('C'), small_blocks.flatten('C')) )
        return toReturn
        
##class used to handle Reed Solomon encoding of IL2P frame payloads 
class FramePayloadDecoder:

    def __init__(self):
        self.ecc_sym_cnt = 50 #the number of error correction symbols to be appended to each block
        self.rsc = RSCodec(self.ecc_sym_cnt)  # the Reed Solomon encoder/decoder object
    
    
    ## @brief perform Solomon Reed decoding on an IL2P frame payload
    ## @param msg A numpy 1-dimensional array of bytes holding the frame to be decoded
    ## @param len_exp The length (in bytes) that the frame is expected to have after it has been decoded. This information is included in the IL2P header
    ## @return Returns a tuple, the first element is a boolean indicating if decoding was completely successful, the second element contains a numpy 
    ## 1-dimensional array of bytes holding the decoding frame data if errors can be corrected
    ## returns an error if Solomon Reed decoding is not successful
    def decode(self,msg,len_exp,verbose=True):
        if (len_exp == 0):
            return (True,np.array([],dtype=np.uint8))
        block_cnt = ceil(len_exp/205) #the number of blocks (up to 255 bytes each) to in msg
        small_block_len = floor(len_exp/block_cnt) #the length (in bytes) of a small block
        large_block_len = small_block_len + 1 #the length (in bytes) of a large block
        large_block_cnt = len_exp - (block_cnt*small_block_len) #the number of large blocks used
        small_block_cnt = block_cnt - large_block_cnt #the number of small blocks used
        
        ecc_sym_cnt = floor(small_block_len/5) + 10 #the number of error correction symbols appended to each block
        
        if (ecc_sym_cnt != self.ecc_sym_cnt):
            self.ecc_sym_cnt = ecc_sym_cnt
            self.rsc = RSCodec(ecc_sym_cnt)
            
        toReturn = np.zeros((len_exp),dtype=np.uint8)
        decodeSuccess = True
        msg_ind = 0 #the current index of msg that is being decoded
        toReturn_ind = 0 #the current index of toReturn that has data being stored to it
        
        error_logging_tuples = [] #make an array of tuples that stores the number of errors corrected for each block that is decoded, -1 errors indicates the frame could not be decoded
        
        #decode the large blocks in msg
        for i in range(0, large_block_cnt):
            try:
                decoded, _ , error_ind = self.rsc.decode(msg[msg_ind:msg_ind+large_block_len+ecc_sym_cnt])
                temp = np.frombuffer(decoded, dtype=np.uint8) #decode the large block
                toReturn[toReturn_ind:toReturn_ind+large_block_len] = temp
                error_logging_tuples.append(('L'+str(i), len(error_ind)))
            except ReedSolomonError:
                error_logging_tuples.append('L'+str(i), -1)
                decodeSuccess = False
                
            msg_ind += large_block_len+ecc_sym_cnt
            toReturn_ind += large_block_len
            
        #decode the small blocks in msg
        for i in range(0, small_block_cnt):
            try:
                decoded, _ , error_ind = self.rsc.decode(msg[msg_ind:msg_ind+small_block_len+ecc_sym_cnt])
                temp = np.frombuffer(decoded, dtype=np.uint8) #decode the large block
                toReturn[toReturn_ind:toReturn_ind+small_block_len] = temp
                error_logging_tuples.append(('S'+str(i), len(error_ind)))
            except ReedSolomonError:
                error_logging_tuples.append(('S'+str(i), -1))
                
                decodeSuccess = False

            msg_ind += small_block_len + ecc_sym_cnt
            toReturn_ind += small_block_len
        
        #if (verbose):
        log.info('\tdecode report: %s',error_logging_tuples)
            
        return (decodeSuccess, toReturn)
            
            
def inject_symbol_errors(msg,error_threshhold):
    for i in range(0, msg.size):
        if (np.random.uniform(0,1) > error_threshhold):
            msg[i] = np.random.bytes(1)[0]
    return msg  
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
        