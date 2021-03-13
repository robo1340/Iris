import functools
import itertools
import logging
import time
from detect import Detector

import numpy as np
from func_timeout import func_set_timeout

import dsp
import common
#import equalizer
import exceptions
#import sampling

from kivy.logger import Logger as log

def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            log.info('%r  %2.2f ms' % (method.__name__, (te - ts) * 1000))
        return result
    return timed

class Receiver:

    def __init__(self, config):
        self.modem = dsp.MODEM(config.symbols)
        self.frequencies = np.array(config.frequencies)
        self.omegas = 2 * np.pi * self.frequencies / config.Fs
        self.omega = 2 * np.pi * config.Fc / config.Fs
        self.Nsym = config.Nsym
        self.Tsym = config.Tsym
        self.iters_per_update = 100  # [ms]
        self.modem_bitrate = config.modem_bps
        self.carrier_index = config.carrier_index
        self.bit_packer = common.BitPacker()

    def run(self, signal,  gain, output):
        ##@brief private method to convert a DBPSK signal to bits
        ##@param signal an iterable signal
        ##@return yields a stream of bits
        def to_bits(signal):
            t = np.arange(self.Nsym)
            p_prev = common.take(signal, self.Nsym)*np.cos(2*np.pi*t*self.omega) 
            
            #take one symbol worth of samples and run it through a bandpass filter set to the carrier frequency
            for offset, buf in common.iterate(signal, self.Nsym, index=True):
                #take one symbol worth of signal and run it through a bandpass filter set to the carrier frequency
                p = buf*np.cos(2*np.pi*t*self.omega)
                z = np.sum(p * p_prev) #numerically integrate the product of the current symbol and the previous symbol
                phase_changed = (z < 0) #if the result is negative, the phase changed between these two symbols
                p_prev = p
                if (phase_changed): #this marks a '1'
                    yield 1
                else:
                    yield 0
        
        ##@brief turn a bit stream into a byte stream
        ##@param bits, an interable stream of bits
        def to_bytes(bits):
            for chunk in common.iterate(data=bits, size=8, func=tuple, truncate=True):
                yield [self.bit_packer.to_byte[chunk]]

        #this is where the receiver sends its output to the IL2P layer
        output.reset()
        for byte in itertools.chain.from_iterable(to_bytes(to_bits(signal))):
            (received, remaining) = output.addByte(byte) 
            #log.info('recv 0x%x' % (byte,))
            
            if ((received == -1) and (remaining == -1)): #an error occurred while decoding the frame
                raise exceptions.IL2PHeaderDecodeError
            elif (remaining == 0): #all bytes have been received
                raise exceptions.EndOfFrameDetected


