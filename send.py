import itertools
import logging

import numpy as np

import common
import equalizer
import dsp

log = logging.getLogger(__name__)

class Sender:
    def __init__(self, fd, config, gain=1.0):
        self.gain = gain
        self.offset = 0
        self.fd = fd
        self.modem = dsp.MODEM(config.symbols)
        self.carriers = config.carriers / config.Nfreq
        self.pilot = config.carriers[config.carrier_index]
        self.silence = np.zeros(equalizer.silence_length * config.Nsym)
        self.iters_per_report = config.baud  # report once per second
        self.padding = [0] * config.bits_per_baud
        self.equalizer = equalizer.Equalizer(config)

    def write(self, sym):
        sym = np.array(sym) * self.gain
        data = common.dumps(sym)
        self.fd.write(data)
        self.offset += len(sym)

    def start(self):
        for value in equalizer.carrier_preamble:
            self.write(self.pilot * value)

        symbols = self.equalizer.train_symbols(equalizer.equalizer_length)
        signal = self.equalizer.modulator(symbols)
        self.write(self.silence) #prefix
        self.write(signal) #train symbols
        self.write(self.silence) #postfix
                
    ##@brief modulates and sends a stream of bytes to self.fd
    ##@param data an iterable stream of bytes
    def modulate(self, data):
        bits = itertools.chain.from_iterable(self.__encode_to_bits(data))
        bits = itertools.chain(bits, self.padding)
        Nfreq = len(self.carriers)
        symbols_iter = common.iterate(self.modem.encode(bits), size=Nfreq)
        for i, symbols in enumerate(symbols_iter, 1):
            self.write(np.dot(symbols, self.carriers))
            if i % self.iters_per_report == 0:
                total_bits = i * Nfreq * self.modem.bits_per_symbol
                log.debug('Sent %10.3f kB', total_bits / 8e3)
    
    ##@brief private method to convert a stream of bytes to bits
    ##@param data an iterable stream of bytes
    ##@return yields a stream of bits
    def __encode_to_bits(self, data):
        converter = common.BitPacker()
        for frame in common.iterate(data=data, size=50, func=bytearray, truncate=False):
            for byte in frame:
                #print (converter.to_bits[byte])
                yield converter.to_bits[byte]
