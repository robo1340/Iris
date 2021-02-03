"""Signal detection capabilities for amodem."""

import collections
import itertools
import logging
import time

import numpy as np

import dsp
import equalizer
import common
from common import Status
import exceptions

from kivy.logger import Logger as log

class Detector:

    COHERENCE_THRESHOLD = 0.75
    CARRIER_THRESHOLD = int(0.03 * equalizer.carrier_length)

    def __init__(self, config, pylab):
        self.freq = config.Fc
        self.omega = 2 * np.pi * self.freq / config.Fs
        self.Nsym = config.Nsym
        self.Tsym = config.Tsym
        self.maxlen = config.baud  # 1 second of symbols
        self.max_offset = config.timeout * config.Fs

    def _wait(self, samples, stat_update):
        counter = 0
        bufs = collections.deque([], maxlen=self.maxlen)
        for offset, buf in common.iterate(samples, self.Nsym, index=True):
            #buf = buf*6
            coeff = dsp.coherence(buf, self.omega)
            if abs(coeff) > self.COHERENCE_THRESHOLD:
                counter += 1
                bufs.append(buf)
                #if (abs(coeff) > 0.5):
                #    print(abs(coeff))
                #if (counter > 1):
                #    print(counter)
                #if (counter > 3):
                #    stat_update.update_status(Status.SQUELCH_CONTESTED)
                
            else:
                bufs.clear()
                counter = 0
                if offset > self.max_offset:
                    raise exceptions.NoCarrierDetectedError

            if counter == self.CARRIER_THRESHOLD:
                return np.concatenate(bufs)

        raise exceptions.NoCarrierDetectedError

    def _prefix(self, signal, gain=1.0):
        silence_found_ind = 0
        silence_found = False
        ind = 0
        i=0
        #for i in range(0, len(equalizer.carrier_preamble)+1):
        for buf in common.iterate(signal, self.Nsym):
            
            coeff = dsp.coherence(buf, self.omega)
            bit = 1 if (abs(coeff) > Detector.COHERENCE_THRESHOLD) else 0
            if (silence_found == False):
                if (bit == 0):
                    silence_found = True
                    silence_found_ind = i
                elif(bit != 1):
                    log.warning('WARNING: prefix symbol that is not 0 or 1 found')                   
            elif (silence_found == True):
                #if (bit == 0):
                if ((i - silence_found_ind) >= equalizer.carrier_silence_length):
                    break

            if (i == len(equalizer.carrier_preamble)):
                log.warning('WARNING: prefix reader timed out')
                break
            else:
                i += 1
    
    ##@brief detects the carrier sine wave that is sent first
    def run(self, samples, stat_update):
        buf = self._wait(samples, stat_update)

        amplitude = self.estimate(buf)
        gain = 1.0 / amplitude
        
        self._prefix(samples,gain)
        #log.debug('Carrier symbols amplitude- %0.3f | Frequency Error- %0.3f ppm' % (amplitude, freq_err*1e6))
        
        return gain#, freq_err

    def estimate(self, buf, skip=3):
        filt = dsp.exp_iwt(-self.omega, self.Nsym) / (0.5 * self.Nsym)
        frames = common.iterate(buf, self.Nsym)
        symbols = [np.dot(filt, frame) for frame in frames]
        symbols = np.array(symbols[skip:-skip])

        amplitude = np.mean(np.abs(symbols))

        phase = np.unwrap(np.angle(symbols)) / (2 * np.pi)
        indices = np.arange(len(phase))
        a, b = dsp.linear_regression(indices, phase)

        #freq_err = a / (self.Tsym * self.freq)

        return amplitude#, freq_err
