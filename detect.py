"""Signal detection capabilities for amodem."""

import collections
import itertools
import logging
import time
import random

import numpy as np

import dsp
#import equalizer
import common
import exceptions

from kivy.logger import Logger as log

class MooreMachine:
    
    def __init__(self):
        self.state_transition_array = [True, True, True, True, True, False, False, True, True, False, True, False, True] 
        self.current_state = 0
    
    ##@brief feed a boolean input into the Moore Machine
    ##@param bool_in the boolean input into the Moore Machine
    ##@return returns the output of the Moore Machine
    def feed(self, bool_in):
        if (bool_in == self.state_transition_array[self.current_state]): #transition to the next state if the input was correct
            self.current_state += 1
        else: #reset the machine if the input was not correct
            self.current_state = 0
        
        #compute the output of the Moore Machine
        if (self.current_state == len(self.state_transition_array)):
            self.current_state = 0
            return True
        else:
            return False
        
class Detector:

    COHERENCE_THRESHOLD = 0.75
    CARRIER_THRESHOLD = 10 #number of milliseconds the carrier needs to be coherently detected
    #CARRIER_THRESHOLD = int(0.03 * equalizer.carrier_length)

    def __init__(self, config):
        self.freq = config.Fc
        self.samp_freq = config.Fs
        #log.info(config.Fs)
        self.omega = 2 * np.pi * self.freq / self.samp_freq
        self.Nsym = config.Nsym
        self.Tsym = config.Tsym
        self.maxlen = config.baud  # 1 second of symbols
        self.max_offset = config.timeout * self.samp_freq
        self.avg_timeout = 0.5
        #self.equalizer = equalizer.Equalizer(config)
        self.barker_detector = MooreMachine()

    def _wait(self, samples):
        timeout_sec = self.avg_timeout + 0.5*random.uniform(-self.avg_timeout,self.avg_timeout)
        bufs = collections.deque([], maxlen=self.CARRIER_THRESHOLD)
        for offset, buf in common.iterate(samples, self.Nsym, index=True):
            #look for a signal that is coherent with the carrier wave
            if (abs(dsp.coherence(buf, self.omega)) > self.COHERENCE_THRESHOLD):
                bufs.append(buf)
                #log.info(len(bufs))
                if (len(bufs) == self.CARRIER_THRESHOLD):
                    log.info('coherence threshhold reached')
                    return np.concatenate(bufs)
            else: #reset the buffer if the sample is not coherent
                bufs.clear()
                if (offset > 0.5*self.samp_freq):#(self.max_offset)):
                    raise exceptions.NoCarrierDetectedError  
        raise exceptions.NoCarrierDetectedError

    def _prefix(self, samples, gain=1.0):
        t = np.arange(self.Nsym)

        #take one symbol worth of samples and run it through a bandpass filter set to the carrier frequency
        p_prev = common.take(samples, self.Nsym)*np.cos(2*np.pi*t*self.omega) 

        for offset, buf in common.iterate(samples, self.Nsym, index=True):
            #take one symbol worth of samples and run it through a bandpass filter set to the carrier frequency
            p = buf*np.cos(2*np.pi*t*self.omega)
            z = np.sum(p * p_prev) #numerically integrate the product of the current symbol and the previous symbol
            phase_changed = (z < 0) #if the result is negative, the phase changed between these two symbols
            if (self.barker_detector.feed(phase_changed)==True):
                log.info('barker code detected')
                return True
            elif (offset > self.max_offset):
                return False
            p_prev = p

    ##@brief detects the carrier sine wave that is sent first
    ##@return if a carrier is detected, returns a gain factor to use, returns -1 otherwise
    def run(self, samples, stat_update):
        buf = self._wait(samples)

        amplitude = self.estimate(buf)
        gain = 1.0 / amplitude
        
        #log.debug('Carrier symbols amplitude- %0.3f | Frequency Error- %0.3f ppm' % (amplitude, freq_err*1e6))
        if (self._prefix(samples,gain)):
            return gain
        else:
            return -1

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
