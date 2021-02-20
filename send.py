import itertools
import logging

import numpy as np

import common
import equalizer
import dsp

from kivy.logger import Logger as log

class Sender:
    def __init__(self, fd, config, carrier_length=750):
        self.gain = 1.0
        self.offset = 0
        self.fd = fd
        self.modem = dsp.MODEM(config.symbols)
        self.carriers = config.carriers / config.Nfreq
        self.pilot = config.carriers[config.carrier_index]
        self.silence = np.zeros(equalizer.silence_length * config.Nsym)
        self.iters_per_report = config.baud  # report once per second
        self.padding = [0] * config.bits_per_baud
        
        self.equalizer = equalizer.Equalizer(config)
        train_symbols = self.equalizer.train_symbols(equalizer.equalizer_length)
        self.train_signal = self.equalizer.modulator(train_symbols)
        
        self.barker_symbols = [-1, 1, 1, 1,-1,-1,-1, 1,-1,-1, 1,-1]
        self.barker_signal = np.concatenate(self.equalizer.modulator(self.barker_symbols))
        self.carrier_length = carrier_length
        self.bit_packer = common.BitPacker()

    def write(self, signal):
        signal = np.array(signal) * self.gain
        data = common.dumps(signal)
        self.fd.write(data)
        self.offset += len(signal)

    def start(self):
        for i in range(0,self.carrier_length): #transmit the pilot signal
            self.write(self.pilot)
        
        self.write(self.barker_signal) #transmit the synchronization signal
        
        self.write(self.train_signal) #transmit the training prefix
                
    ##@brief modulates and sends a stream of bytes to self.fd
    ##@param data an iterable stream of bytes
    def modulate(self, data):
        
        ##@brief private method to convert a stream of bytes to bits
        ##@param data an iterable stream of bytes
        ##@return yields a stream of bits
        def to_bits(data):
            for byte_arr in common.iterate(data=data, size=1, func=bytearray, truncate=False):
                yield self.bit_packer.to_bits[byte_arr[0]]
        
        bits = itertools.chain.from_iterable( to_bits(data) )
        bits = itertools.chain(bits, self.padding)
        Nfreq = len(self.carriers)
        symbols_iter = common.iterate(self.modem.encode(bits), size=Nfreq)
        for i, symbols in enumerate(symbols_iter, 1):
            self.write(np.dot(symbols, self.carriers))
            if i % self.iters_per_report == 0:
                total_bits = i * Nfreq * self.modem.bits_per_symbol
                log.info('Sent %10.3f kB', total_bits / 8e3)
    

