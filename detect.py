"""Signal detection capabilities for amodem."""

import collections
import itertools
import logging
import time

import numpy as np

import dsp
import equalizer
import common
import exceptions

log = logging.getLogger(__name__)


class Detector:

    COHERENCE_THRESHOLD = 0.9

    CARRIER_DURATION = equalizer.equalizer_length
    CARRIER_THRESHOLD = int(0.1 * CARRIER_DURATION)
    SEARCH_WINDOW = int(0.1 * CARRIER_DURATION)
    START_PATTERN_LENGTH = SEARCH_WINDOW // 4

    def __init__(self, config, pylab):
        self.freq = config.Fc
        self.omega = 2 * np.pi * self.freq / config.Fs
        self.Nsym = config.Nsym
        self.Tsym = config.Tsym
        self.maxlen = config.baud  # 1 second of symbols
        self.max_offset = config.timeout * config.Fs
        self.plt = pylab

    def _wait(self, samples):
        counter = 0
        bufs = collections.deque([], maxlen=self.maxlen)
        for offset, buf in common.iterate(samples, self.Nsym, index=True):

            coeff = dsp.coherence(buf, self.omega)
            if abs(coeff) > self.COHERENCE_THRESHOLD:
                counter += 1
                bufs.append(buf)
            else:
                bufs.clear()
                counter = 0
                if offset > self.max_offset:
                    raise exceptions.NoCarrierDetectedError

            if counter == self.CARRIER_THRESHOLD:
                return offset, bufs

        raise exceptions.NoCarrierDetectedError

    ##@brief detects the carrier sine wave that is sent first
    def run(self, samples):
        offset, bufs = self._wait(samples)

        length = (self.CARRIER_THRESHOLD - 1) * self.Nsym
        begin = offset - length

        start_time = begin * self.Tsym / self.Nsym
        #print('Carrier detected at ~%.1f ms @ %.1f kHz' % (start_time * 1e3, self.freq / 1e3))
        #print('Buffered %d ms of audio'%(len(bufs)))

        buf = np.concatenate(bufs)

        prefix_length = self.CARRIER_DURATION * self.Nsym
        amplitude, freq_err = self.estimate(buf)
        print('Amplitude: %f | Frequency Error: %f' % (amplitude, freq_err))
        return itertools.chain(buf, samples), amplitude, freq_err

    def estimate(self, buf, skip=5):
        filt = dsp.exp_iwt(-self.omega, self.Nsym) / (0.5 * self.Nsym)
        frames = common.iterate(buf, self.Nsym)
        symbols = [np.dot(filt, frame) for frame in frames]
        symbols = np.array(symbols[skip:-skip])

        amplitude = np.mean(np.abs(symbols))
        log.debug('Carrier symbols amplitude : %.3f', amplitude)

        phase = np.unwrap(np.angle(symbols)) / (2 * np.pi)
        indices = np.arange(len(phase))
        a, b = dsp.linear_regression(indices, phase)
        self.plt.figure()
        self.plt.plot(indices, phase, ':')
        self.plt.plot(indices, a * indices + b)

        freq_err = a / (self.Tsym * self.freq)
        log.debug('Frequency error: %.3f ppm', freq_err * 1e6)
        self.plt.title('Frequency drift: {0:.3f} ppm'.format(freq_err * 1e6))
        return amplitude, freq_err
