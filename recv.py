import functools
import itertools
import logging
import time
from detect import Detector

import numpy as np
from func_timeout import func_set_timeout

import dsp
import common
import equalizer
import exceptions
import sampling

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
        self.equalizer = equalizer.Equalizer(config)
        self.carrier_index = config.carrier_index
        self.freq_err_gain = 0.01 * self.Tsym  # integration feedback gain
        self.train_symbols = self.equalizer.train_symbols(equalizer.equalizer_length)
        self.train_signal = (self.equalizer.modulator(self.train_symbols) * len(self.frequencies))
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
        
    #@timeit
    def _train(self, sampler, order):
        signal_length = equalizer.equalizer_length * self.Nsym
        observed_signal = sampler.take(signal_length)
        
        #use the observed prefix signal and the expected prefix signal to train an equalizer filter
        coeffs = equalizer.train(signal = observed_signal, expected=self.train_signal, order=order)
        equalization_filter = dsp.FIR(h=coeffs)
        
        #run the observed signal through the equalizer
        equalized_signal = list(equalization_filter(observed_signal))
        
        self._verify_training(equalized_signal, self.train_symbols)
        return equalization_filter

    #@timeit
    def _verify_training(self, equalized, train_symbols):
        symbols = self.equalizer.demodulator(equalized, equalizer.equalizer_length)
        sliced = np.array(symbols).round()
        errors = np.array(sliced - train_symbols, dtype=np.bool)
        error_rate = errors.sum() / errors.size

        errors = np.array(symbols - train_symbols)

        noise_rms = dsp.rms(errors)
        signal_rms = dsp.rms(train_symbols)
        SNRs = 20.0 * np.log10(signal_rms / noise_rms)
        
        if (error_rate > 0.1):
            log.warning('WARNING!: error rate during training is %4.1f%%' % (error_rate*100))
        else:
            log.debug('Training verified, error rate is %4.1f%%' % (error_rate*100))

    ##@brief method that takes a stream of OFDM symbols and yields a stream of bits
    ##@param symbols an iterable stream of symbols to read from
    def _demodulate(self, symbols):
        symbol_list = []
        errors = {}
        #noise = {}

        ##@brief internal method used to keep track of the distance between the symbol received and ideal symbol
        ## so that the sampler can be updated to correct for errors
        def error_handler(received, decoded, freq):
            errors.setdefault(freq, []).append(received / decoded)
            #noise.setdefault(freq, []).append(received - decoded)

        stream, symbol_list = self._bitstream(symbols, error_handler)

        log.debug('Starting demodulation')
        for i, block_of_bits in enumerate(stream, 1):
            for bits in block_of_bits:
                yield bits

            if i % self.iters_per_update == 0:
                self._update_sampler(errors, symbols.sampler)
            
            
    def _bitstream(self, symbols, error_handler):
        streams = []
        symbol_list = []
        generators = common.split(symbols, n=len(self.omegas))
        for freq, S in zip(self.frequencies, generators):
            equalized = []
            S = common.icapture(S, result=equalized)
            symbol_list.append(equalized)

            #create a version of error_handler that automatically has freq passed in
            freq_handler = functools.partial(error_handler, freq=freq) 
            
            bits = self.modem.decode(S, freq_handler)  # list of bit tuples
            streams.append(bits)  # bit stream per frequency

        return common.izip(streams), symbol_list

    def _update_sampler(self, errors, sampler):
        err = np.array([e for v in errors.values() for e in v])
        err = np.mean(np.angle(err))/(2*np.pi) if err.size else 0
        errors.clear()

        sampler.freq -= self.freq_err_gain * err
        sampler.offset -= err


