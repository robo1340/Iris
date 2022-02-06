""" Common package functionality.
Commom utilities and procedures for amodem.

"""

import itertools
import logging
import async_reader
import threading
import sys
import os
import pickle

import numpy as np

import kivy.utils

CONFIG_FILE = 'config.pickle'
MESSAGE_FILE = 'messages.pickle'

STATUS_IND_FILE = 'status_ind.pickle'
STATISTICS_FILE = 'statistics.pickle'
SIGNAL_STRENGTH_FILE = 'signal_strength.pickle'
MY_WAYPOINTS_FILE = 'my_waypoints.pickle'

from kivy.logger import Logger as log

scaling = 32000.0  # out of 2**15

##@brief a specific version of exception_suppressor
## that will only catch a specific type of exception and
## prints a user defined error message upon catching it as a warning
##@param func the function to run
##@param e the exception to catch
##@param msg the error message to print if the exception is caught
def exception_suppressor(e=BaseException, msg=None):
    def decorator(func):
        def meta_function(*args, **kwargs):
            try:
                func(*args,**kwargs)
            except e as ex:
                if (msg is not None):
                    log.error(msg)
                else:
                    log.error('Exception caught by exception_suppressor()')
                    log.error(ex)
        return meta_function
    return decorator

## @brief simple container to put relevant statics and log items as the program runs
class Stats():
    def __init__(self):
        self.txs = 0 ##tx success count
        self.txf = 0 ##rx failure count
        self.rxs = 0 ##rx success count
        self.rxf = 0 ##rx failure count

def generate_bind_addr(num, base_port):
    addrs = []
    for i in range(0,num):
        addr = "tcp://*:" + str(base_port+i)
        addrs.append(addr)
    return addrs

def generate_connect_addr(num, base_port):
    addrs = []
    for i in range(0,num):
        addr = "tcp://127.0.0.1:" + str(base_port+i)
        addrs.append(addr)
    return addrs
        
SQUELCH_CONTESTED = "squelch_contested"
SQUELCH_OPEN = "squelch_open"
CARRIER_DETECTED = "carrier_detected"
SQUELCH_CLOSED = "squelch_closed"
MESSAGE_RECEIVED = "message_received"
TRANSMITTING = "transmitting"

def load_message_file(return_if_empty=[]):
    if os.path.isfile('./' + MESSAGE_FILE):
        with open(MESSAGE_FILE, 'rb') as f:
            return pickle.load(f)
    else:
        return return_if_empty

def update_message_file(new_messages):
    with open(MESSAGE_FILE, 'wb') as f:
        pickle.dump(new_messages, f)

def updateConfigFile(new_config):
    with open(CONFIG_FILE, 'wb') as f:
        pickle.dump(new_config, f)

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

class BitPacker:
    def __init__(self):
        bits_list = []
        for index in range(2 ** 8): #iterate over every possible byte value, 0 through 255
            bits = [index & (2 ** k) for k in range(8)] #create an array of bits corresponding to the given index
            bits_list.append(tuple((1 if b else 0) for b in bits))

        #create a dictionary to convert a given byte to a tuple of bits
        #the dictionary key, i is the byte value to convert
        #the dictionary value, bits is a tuple of 8 bit values
        self.to_bits = dict((i, bits) for i, bits in enumerate(bits_list))
        
        #create a dictionary to convert a given tuple of bits to a byte value
        #the dictionary key, bits is a tuple of 8 bits
        #the dictionary value, i is the byte value
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
    """ Take 1 element from iterable, and return it """
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
