"""Asynchronous Reading capabilities for amodem."""

#import logging
import threading
import queue
import time
import numpy as np
from collections import deque
import math

from kivy.logger import Logger as log

class AsyncReader:
    def __init__(self, stream, mean_abs_callback):
        self.stream = stream
        self.queue = queue.Queue()
        self.stop = threading.Event()
        args = (stream, stream.bufsize, self.queue, self.stop, mean_abs_callback)
        self.thread = threading.Thread(target=AsyncReader._thread, args=args, name='AsyncReader')
        self.thread.start()
        self.buf = b''

    @staticmethod
    def _thread(src, bufsize, queue, stop, mean_abs_callback):
        try:
            log.debug('AsyncReader thread started')
            while not stop.isSet():
                buf = src.read(bufsize)
                #if (mean is not None):
                #    log.info('Mean %d' % (mean,) )
                
                #compute the mean of the absolute value of the samples taken and pass them to a callback method
                arr = np.frombuffer(buf, dtype='int16')
                mean_abs_callback(np.mean(np.abs(arr)))
                
                if (queue.full()):
                    time.sleep(0.01)
                    log.info('queue is full')
                    queue.get()
                    
                queue.put(buf)
                
            log.debug('AsyncReader thread stopped')
        except BaseException:  # pylint: disable=broad-except
            log.exception('AsyncReader thread failed')
            queue.put(None)

    def read(self, size):
        while len(self.buf) < size:
            buf = self.queue.get()
            if buf is None:
                raise IOError('cannot read from stream')
            self.buf += buf

        result = self.buf[:size]
        self.buf = self.buf[size:]
        return result

    def close(self):
        if self.stream is not None:
            self.stop.set()
            self.thread.join()
            self.stream.close()
            self.stream = None
