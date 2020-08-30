import functools
import itertools
import logging
import time

import numpy as np
from func_timeout import func_set_timeout

import dsp
import common
import equalizer
import exceptions

log = logging.getLogger(__name__)


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print ('%r  %2.2f ms' % (method.__name__, (te - ts) * 1000))
        return result
    return timed


class Receiver:

    def __init__(self, config, pylab=None):
        self.stats = {}
        self.plt = pylab
        self.modem = dsp.MODEM(config.symbols, config.squelch)
        self.frequencies = np.array(config.frequencies)
        self.omegas = 2 * np.pi * self.frequencies / config.Fs
        self.Nsym = config.Nsym
        self.Tsym = config.Tsym
        self.iters_per_update = 100  # [ms]
        self.iters_per_report = 1000  # [ms]
        self.modem_bitrate = config.modem_bps
        self.equalizer = equalizer.Equalizer(config)
        self.carrier_index = config.carrier_index
        self.output_size = 0  # number of bytes written to output stream
        self.freq_err_gain = 0.01 * self.Tsym  # integration feedback gain

    ##@brief the prefix is a carrier wave followed by a short period of silence. Some of the carrier wave will be cut off as the receiving radio's squelch is turned off.
    ## this method will read in the carrier wave (represented by a value of 1), then will read in the silent period to ensure the reciever is synchronized to the frame
    ##@param symbols the symbol iterator
    ##@param gain the gain to be applied to each symbol, defaults to 1.0
    def _prefix(self, symbols, gain=1.0):
        silence_found_ind = 0
        silence_found = False
        ind = 0
        for i in range(0, len(equalizer.carrier_preamble)+1):
            S = common.take(symbols, 1)
            S = S[:, self.carrier_index] * gain
            sliced = np.round(np.abs(S))
            bit = np.array(sliced[0], dtype=int)
            
            if (silence_found == False):
                if (bit == 0):
                    silence_found = True
                    silence_found_ind = i
                    #log.info(i)
                elif(bit != 1):
                    log.warning('WARNING: prefix symbol that is not 0 or 1 found')                   
            elif (silence_found == True):
                #if (bit == 0):
                if ((i - silence_found_ind) >= equalizer.carrier_silence_length):
                    break
                #else:
                    #log.warning('WARNING: prefix carrier silence period ended prematurely')

            if (i == len(equalizer.carrier_preamble)):
                log.warning('WARNING: prefix reader timed out')
                break
    #@timeit
    def _train(self, sampler, order, lookahead):
        equalizer_length = equalizer.equalizer_length
        train_symbols = self.equalizer.train_symbols(equalizer_length)
        #print(train_symbols)
        train_signal = (self.equalizer.modulator(train_symbols) * len(self.frequencies))

        prefix = postfix = equalizer.silence_length * self.Nsym
        signal_length = equalizer_length * self.Nsym + prefix + postfix

        signal = sampler.take(signal_length + lookahead)
        #print(signal)

        coeffs = equalizer.train(
            signal=signal[prefix:-postfix], #only look at the part of the signal containing the training symbols
            expected=np.concatenate([train_signal, np.zeros(lookahead)]),
            order=order, lookahead=lookahead
        )

        equalization_filter = dsp.FIR(h=coeffs)
        log.debug('Training completed')
        # Pre-load equalization filter with the signal (+lookahead)
        equalized = list(equalization_filter(signal))
        equalized = equalized[prefix+lookahead:-postfix+lookahead]
        self._verify_training(equalized, train_symbols)
        return equalization_filter

    #@timeit
    def _verify_training(self, equalized, train_symbols):
        equalizer_length = equalizer.equalizer_length
        symbols = self.equalizer.demodulator(equalized, equalizer_length)
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

    def _bitstream(self, symbols, error_handler):
        streams = []
        symbol_list = []
        generators = common.split(symbols, n=len(self.omegas))
        for freq, S in zip(self.frequencies, generators):
            equalized = []
            S = common.icapture(S, result=equalized)
            symbol_list.append(equalized)

            freq_handler = functools.partial(error_handler, freq=freq)
            bits = self.modem.decode(S, freq_handler)  # list of bit tuples
            streams.append(bits)  # bit stream per frequency

        return common.izip(streams), symbol_list

    def _demodulate(self, sampler, symbols):
        symbol_list = []
        errors = {}
        noise = {}

        def _handler(received, decoded, freq):
            errors.setdefault(freq, []).append(received / decoded)
            noise.setdefault(freq, []).append(received - decoded)

        stream, symbol_list = self._bitstream(symbols, _handler)
        self.stats['symbol_list'] = symbol_list
        self.stats['rx_bits'] = 0
        self.stats['rx_start'] = time.time()

        log.debug('Starting demodulation')
        for i, block_of_bits in enumerate(stream, 1):
            for bits in block_of_bits:
                self.stats['rx_bits'] = self.stats['rx_bits'] + len(bits)
                yield bits

            if i % self.iters_per_update == 0:
                self._update_sampler(errors, sampler)

    def _update_sampler(self, errors, sampler):
        err = np.array([e for v in errors.values() for e in v])
        err = np.mean(np.angle(err))/(2*np.pi) if err.size else 0
        errors.clear()

        sampler.freq -= self.freq_err_gain * err
        sampler.offset -= err

    @func_set_timeout(15)
    def run(self, sampler, gain, output):
        symbols = dsp.Demux(sampler, omegas=self.omegas, Nsym=self.Nsym)
        
        log.debug('Carrier Detected: Receiving')
        self._prefix(symbols, gain=gain)

        filt = self._train(sampler, order=10, lookahead=10) #train the equalizer filter
        sampler.equalizer = lambda x: list(filt(x))

        bitstream = self._demodulate(sampler, symbols)
        bitstream = itertools.chain.from_iterable(bitstream)

        #this is where the receiver sends its output to the IL2P layer
        output.reset()
        converter = common.BitPacker()
        for byte in itertools.chain.from_iterable(_to_bytes(bitstream, converter)):	
            (received, remaining) = output.addByte(byte)
            self.output_size += 1   
            
            if ((received == -1) and (remaining == -1)): #an error occurred while decoding the frame
                raise exceptions.IL2PHeaderDecodeError
            elif (remaining == 0):
                raise exceptions.EndOfFrameDetected

    def report(self):
        if self.stats:
            duration = time.time() - self.stats['rx_start']
            audio_time = self.stats['rx_bits'] / float(self.modem_bitrate)
            log.debug('Demodulated %.3f kB @ %.3f seconds (%.1f%% realtime)', self.stats['rx_bits'] / 8e3, duration, 100 * duration / audio_time if audio_time else 0)
            #log.info('Received %.3f kB @ %.3f seconds = %.3f kB/s', self.output_size * 1e-3, duration, self.output_size * 1e-3 / duration)

#@timeit
def _to_bytes(bits, converter):
    for chunk in common.iterate(data=bits, size=8, func=tuple, truncate=True):
        yield [converter.to_byte[chunk]]
