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
                return offset, bufs

        raise exceptions.NoCarrierDetectedError

    ##@brief detects the carrier sine wave that is sent first
    def run(self, samples, stat_update):
        offset, bufs = self._wait(samples, stat_update)

        length = (self.CARRIER_THRESHOLD - 1) * self.Nsym
        begin = offset - length

        start_time = begin * self.Tsym / self.Nsym

        buf = np.concatenate(bufs)

        amplitude = self.estimate(buf)
        #log.debug('Carrier symbols amplitude- %0.3f | Frequency Error- %0.3f ppm' % (amplitude, freq_err*1e6))
        
        return itertools.chain(buf, samples), amplitude#, freq_err

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
