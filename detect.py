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

    CARRIER_DURATION = sum(equalizer.prefix)
    CARRIER_THRESHOLD = int(0.3 * CARRIER_DURATION)
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
            bufs.append(buf)

            coeff = dsp.coherence(buf, self.omega)
            if abs(coeff) > self.COHERENCE_THRESHOLD:
                counter += 1
            else:
                counter = 0
                if offset > self.max_offset:
                    raise exceptions.NoCarrierDetectedError

            if counter == self.CARRIER_THRESHOLD:
                return offset, bufs

        raise exceptions.NoCarrierDetectedError

    ##@brief detects when any signal past the squelch threshhold is being received
    ##@samples iterator used to sample the audio
    ##@squelch the squelch threshhold
    ##@timeout time before raising a SquelchActive exception
    def detect_signal(self, samples, squelch, timeout):
        start = time.time()
        max_buf_len = 500
        buf = collections.deque([], maxlen=max_buf_len)
        
        #while(True):
        while((time.time() - start) < timeout):
            val = common.takeOne(samples) #read the next sample
            if (len(buf) == max_buf_len):
                buf.popleft() #remove the oldest value
            buf.append(val)
            
            if (val > squelch):
                buf = list(buf)
                return itertools.chain(buf, samples)
                    
        raise exceptions.SquelchActive

    ##@brief detects the carrier sine wave that is sent first
    def run(self, samples):
        offset, bufs = self._wait(samples)

        length = (self.CARRIER_THRESHOLD - 1) * self.Nsym
        begin = offset - length

        start_time = begin * self.Tsym / self.Nsym
        log.debug('Carrier detected at ~%.1f ms @ %.1f kHz', start_time * 1e3, self.freq / 1e3)

        log.debug('Buffered %d ms of audio', len(bufs))

        bufs = list(bufs)[-self.CARRIER_THRESHOLD-self.SEARCH_WINDOW:]
        n = self.SEARCH_WINDOW + self.CARRIER_DURATION - self.CARRIER_THRESHOLD
        trailing = list(itertools.islice(samples, n * self.Nsym))
        bufs.append(np.array(trailing))

        buf = np.concatenate(bufs)
        offset = self.find_start(buf)
        start_time += (offset / self.Nsym - self.SEARCH_WINDOW) * self.Tsym
        log.debug('Carrier starts at %.3f ms', start_time * 1e3)

        buf = buf[offset:]

        prefix_length = self.CARRIER_DURATION * self.Nsym
        amplitude, freq_err = self.estimate(buf[:prefix_length])
        return itertools.chain(buf, samples), amplitude, freq_err

    def find_start(self, buf):
        carrier = dsp.exp_iwt(self.omega, self.Nsym)
        carrier = np.tile(carrier, self.START_PATTERN_LENGTH)
        zeroes = carrier * 0.0
        signal = np.concatenate([zeroes, carrier])
        signal = (2 ** 0.5) * signal / dsp.norm(signal)

        corr = np.abs(np.correlate(buf, signal))
        norm_b = np.sqrt(np.correlate(np.abs(buf)**2, np.ones(len(signal))))
        coeffs = np.zeros_like(corr)
        coeffs[norm_b > 0.0] = corr[norm_b > 0.0] / norm_b[norm_b > 0.0]

        index = np.argmax(coeffs)
        log.info('Carrier coherence: %.3f%%', coeffs[index] * 100)
        offset = index + len(zeroes)
        return offset

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
