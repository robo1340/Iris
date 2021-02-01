""" Common package functionality.
Commom utilities and procedures for amodem.

"""

import itertools
import logging
import async_reader
import threading
import sys
import configparser

import numpy as np

import kivy.utils

CONFIG_FILE_NAME = 'config.ini'

log = logging.getLogger(__name__)

scaling = 32000.0  # out of 2**15

def parseConfigFile(config_file_path):
    config = configparser.RawConfigParser()
    config.read(config_file_path)
    return config
	
def verify_ini_config(ini_config):
    toReturn = True #assume the ini file will be ok
    
    properties = ['my_callsign', 'dst_callsign', 'ack_retries', 'ack_timeout', 'tx_cooldown', 
                  'rx_cooldown', 'rx_timeout', 'ack', 'clear', 'scroll', 'master_timeout', 
                  'Fs', 'Npoints', 'carrier_frequency', 'min_wait', 'max_wait']
    
    for p in properties:
        if not (p in ini_config['MAIN']):
            toReturn = False
            log.error('ERROR- %s property not found in .ini config file!' % (p))
            
    return toReturn

##@brief platform type constants
class Platform():
    #platform types
    WIN32 = 1
    WIN64 = 2
    LINUX = 3
    ANDROID = 4

def getPlatform():
    if ((sys.platform == 'win32') and (sys.maxsize > 2**32)): #true if this is a windows 64 bit system
        return Platform.WIN64
    elif ((sys.platform == 'win32') and not (sys.maxsize > 2**32)): #true if this is a windows 32 bit system
        return Platform.WIN32
    elif ((sys.platform == 'linux') and (kivy.utils.platform == 'android')): #true if this is an android system
        return Platform.ANDROID
    elif (sys.platform == 'linux'):
        return Platform.LINUX
    else:
        log.info(sys.platform)
        raise Exception('ERROR: This system is not recognized')

## @brief simple container to put relevant statics and log items as the program runs
class Stats():
    def __init__(self):
        self.txs = 0 ##tx success count
        self.txf = 0 ##rx failure count
        self.rxs = 0 ##rx success count
        self.rxf = 0 ##rx failure count
		
##@brief status constants
class Status():
    #event message values
    SQUELCH_CONTESTED = 6
    SQUELCH_OPEN = 1
    CARRIER_DETECTED = 2
    SQUELCH_CLOSED = 3
    MESSAGE_RECEIVED = 4
    TRANSMITTING = 5

def updateConfigFile(ini_config_parser):
    with open(CONFIG_FILE_NAME, 'w') as configfile:
        ini_config_parser.write(configfile)

class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

def FileType(mode, interface_factory=None):
    def opener(fname):
        audio_interface = interface_factory() if interface_factory else None

        assert 'r' in mode or 'w' in mode
        if audio_interface is None and fname is None:
            fname = '-'

        if fname is None:
            assert audio_interface is not None
            if 'r' in mode:
                s = audio_interface.recorder()
                return async_reader.AsyncReader(stream=s, bufsize=s.bufsize)
            if 'w' in mode:
                return audio_interface.player()

        return open(fname, mode)

    return opener

class BitPacker:
    byte_size = 8

    def __init__(self):
        bits_list = []
        for index in range(2 ** self.byte_size):
            bits = [index & (2 ** k) for k in range(self.byte_size)]
            bits_list.append(tuple((1 if b else 0) for b in bits))
        #print(bits_list)

        self.to_bits = dict((i, bits) for i, bits in enumerate(bits_list))
        self.to_byte = dict((bits, i) for i, bits in enumerate(bits_list))

def load(fileobj):
    """ Load signal from file object. """
    return loads(fileobj.read())


def loads(data):
    """ Load signal from memory buffer. """
    x = np.frombuffer(data, dtype='int16')
    x = x / scaling
    return x


def dumps(sym):
    """ Dump signal to memory buffer. """
    sym = sym.real * scaling
    return sym.astype('int16').tostring()


def iterate(data, size, func=None, truncate=True, index=False):
    """ Iterate over a signal, taking each time *size* elements. """
    offset = 0
    data = iter(data)

    done = False
    while not done:
        buf = list(itertools.islice(data, size))
        if len(buf) < size:
            if truncate or not buf:
                return
            done = True

        result = func(buf) if func else np.array(buf)
        yield (offset, result) if index else result
        offset += size


def split(iterable, n):
    """ Split an iterable of n-tuples into n iterables of scalars.
    The k-th iterable will be equivalent to (i[k] for i in iter).
    """
    def _gen(it, index):
        for item in it:
            yield item[index]

    iterables = itertools.tee(iterable, n)
    return [_gen(it, index) for index, it in enumerate(iterables)]


def icapture(iterable, result):
    """ Appends each yielded item to result. """
    for i in iter(iterable):
        result.append(i)
        yield i


def take(iterable, n):
    """ Take n elements from iterable, and return them as a numpy array. """
    return np.array(list(itertools.islice(iterable, n)))
    
def takeOne(iterable):
    """ Take n elements from iterable, and return them as a numpy array. """
    return (np.array(list(itertools.islice(iterable, 1)))[0])


def izip(iterables):
    """ "Python 3" zip re-implementation for Python 2. """
    iterables = [iter(iterable) for iterable in iterables]
    try:
        while True:
            yield tuple([next(iterable) for iterable in iterables])
    except StopIteration:
        pass


class Dummy:
    """ Dummy placeholder object for testing and mocking. """

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self
