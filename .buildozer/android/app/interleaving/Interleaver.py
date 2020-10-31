import numpy as np

import interleaving.lfsr

#this class will interleave bits fed to it as per the IL2P protocol
class Interleaver:

    def __init__(self):
    
        self.LFSR = interleaving.lfsr.LFSR(fpoly=[9,4], initstate=[0,0,0,0,0,1,1,1,1], outbit_ind=5) #LFSR with polynomial x^9 + x^4 + 1

    def reset(self):
        #self.__init__()
        self.LFSR.reset()
    
    ##@brief interleave the bits in an array of bytes using an LFSR
    ##@param byte_arr, the array of bytes to be interleaved, stored as a 1d numpy array of bytes
    def scramble_bits(self, byte_arr):
        scrambled_bytes = np.zeros((byte_arr.size), dtype=np.uint8)
        
        scrambled_bytes_ind = 0 #index for the current scrambled byte being filled
        j = 7 #index for the current bit of the scrambled byte being filled
        
        #push the bits into the LFSR starting from the most significant bit of the first byte in byte_arr
        for byte_ind in range(0,len(byte_arr)):
            for i in range(7,-1,-1):
                outbit = self.LFSR.next((byte_arr[byte_ind]>>i)&1)
                
                
                if ((byte_ind != 0) or (i<3)): #wait for the first 5 bits to have filled the LFSR before storing the output bit
                    if (outbit == 1): #only set the bit if it is 1
                        scrambled_bytes[scrambled_bytes_ind] = np.uint8(scrambled_bytes[scrambled_bytes_ind] | (outbit<<j))
                    
                    #increment the bit and byte indices for scrambled_bytes if necessary
                    if (j == 0):
                        j = 7
                        scrambled_bytes_ind += 1
                    else:
                        j = j - 1

        #push the last 5 bits through the LFSR
        for i in range(0,5):
            outbit = self.LFSR.next()
            scrambled_bytes[scrambled_bytes_ind] = scrambled_bytes[scrambled_bytes_ind] | (outbit<<j)
            j = j - 1
        
        #print(scrambled_bytes.tobytes().hex())
        return scrambled_bytes
        
#this class will de-interleave bits fed to it as per the IL2P protocol
class Deinterleaver:

    def __init__(self):
        initstate = np.array([1,1,1,1,1,0,0,0,0])
        self.initstate = initstate
        self.state = initstate.astype(int)

    def __next(self,input_bit=0):
        prev_state = self.state
        self.state = np.roll(self.state, 1)
        
        self.state[0] = input_bit
        self.state[5] = np.logical_xor(prev_state[4], input_bit) * 1
        return np.logical_xor(prev_state[8], input_bit) * 1

    def reset(self):
        self.__init__()

    def descramble_bits(self,byte_arr):
        descrambled_bytes = np.zeros((len(byte_arr)), dtype=np.uint8)
        
        descrambled_ind = 0 #index for the current descrambled byte being filled
        j = 7 #index for the current bit of the descrambled byte being filled
        
        #push the bits into the LFSR starting from the most significant bit of the first byte in byte_arr
        for byte_ind in range(0,len(byte_arr)):
            for i in range(7,-1,-1):
                outbit = self.__next((byte_arr[byte_ind]>>i)&1)
                
                if (outbit == 1): #only set the bit if it is 1
                    descrambled_bytes[descrambled_ind] = np.uint8(descrambled_bytes[descrambled_ind] | (outbit<<j))
                
                #increment the bit and byte indices for descrambled_bytes if necessary
                if (j == 0):
                    j = 7
                    descrambled_ind += 1
                else:
                    j = j - 1   
        
        #print(descrambled_bytes.tobytes().hex())
        return descrambled_bytes