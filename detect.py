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

class MooreMachine:
    
    def __init__(self):
        self.state_transition_array = [True, True, False, False, True, False, False, True, True, False, True, True]
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

    def __init__(self, config, pylab):
        self.freq = config.Fc
        #log.info(config.Fs)
        self.omega = 2 * np.pi * self.freq / config.Fs
        self.Nsym = config.Nsym
        self.Tsym = config.Tsym
        self.maxlen = config.baud  # 1 second of symbols
        self.max_offset = config.timeout * config.Fs
        
        self.equalizer = equalizer.Equalizer(config)
        self.barker_symbols = [-1, 1, 1, 1,-1,-1,-1, 1,-1,-1, 1,-1]
        self.barker_detector = MooreMachine()

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

    '''
        def _prefix(self, signal, gain=1.0):
        silence_found_ind = 0
        silence_found = False
        ind = 0
        i=0
        #for i in range(0, len(equalizer.carrier_preamble)+1):
        for buf in common.iterate(signal, self.Nsym):
            
            coeff = dsp.coherence(buf, self.omega)
            bit = 1 if (abs(coeff) > self.COHERENCE_THRESHOLD) else 0
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
    '''
    
    def _prefix(self, samples, gain=1.0):
        silence_found_ind = 0
        silence_found = False
        ind = 0
        i=0
        t = np.arange(self.Nsym)

        buf_prev = common.take(samples, self.Nsym)
        p_prev = buf_prev*np.cos(2*np.pi*t*self.omega)
        
        while(True):
            buf = common.take(samples, self.Nsym) #take the number of samples equal to one DBPSK symbol
            p = buf*np.cos(2*np.pi*t*self.omega) #pass the buffer through a band pass filter set to the carrier frequency
            z = np.sum(p * p_prev)
            phase_changed = (z < 0)
            if (self.barker_detector.feed(phase_changed)==True):
                log.info('barker code detected in the symbol phase changes')
                return True
            
            p_prev = p
            
            if (i == equalizer.carrier_length):
                return False
            else:
                i += 1

    ##@brief detects the carrier sine wave that is sent first
    ##@return if a carrier is detected, returns a gain factor to use, returns -1 otherwise
    def run(self, samples, stat_update):
        buf = self._wait(samples, stat_update)

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
