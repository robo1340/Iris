#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
#import argparse

import sys
import itertools
import logging
import functools
import os
import pickle
import io
import numpy as np
import threading
import time
from queue import PriorityQueue
import wave

sys.path.insert(0,'..') #need to insert parent path to import something from messages

from func_timeout import func_set_timeout, FunctionTimedOut

import pkg_resources
import async_reader
import audio
import common
import send as _send
import recv as _recv
import stream
import detect
import exceptions
import ctypes

import config

import IL2P_API
from transceiver import transceiver_func
from service_controller import ServiceController

from kivy.logger import Logger as log

master_timeout = 20 #sets the timeout for the last line of defense when the program is stuck
tx_cooldown = 1 #cooldown period after the sending in seconds, the program may not transmit for this period of time after transmitting a frame
rx_cooldown = 0.5 #cooldown period after receiving in seconds, the program may not receive or transmit for this period of time after receiving a frame

# Python 3 has `buffer` attribute for byte-based I/O
#_stdin = getattr(sys.stdin, 'buffer', sys.stdin)
#_stdout = getattr(sys.stdout, 'buffer', sys.stdout)

## @brief simple container to put arguments used throughout the program in 
class Args():
    def __init__(self, interface=None):
        self.recv_src = None
        self.recv_dst = None
        self.interface = interface
        
        self.sender_src = None
        self.sender_dst = None
        
        self.input = None
        self.output = None


###################################################################        
#################### Android Device Service########################
################################################################### 
if __name__ == "__main__":
    log.info('start of service')

    #from jnius import autoclass
    #PythonService = autoclass('org.kivy.android.PythonService')
    #PythonService.mService.setAutoRestartService(True)

    cwd = os.path.dirname(os.path.abspath(__file__)) #get the current working directory

    ctypes.CDLL(os.path.join(cwd, 'libgnustl_shared.so'))
    ctypes.CDLL(os.path.join(cwd, 'libportaudio.so'))
    log.debug('libportaudio loaded')
    
    if os.path.isfile('./' + common.CONFIG_FILE):
        with open(common.CONFIG_FILE, 'rb') as f:
            config = pickle.load(f)
    else:
        raise Exception('Error: No config file found')
    

    args = Args(interface=audio.Interface(config).load(os.path.join(cwd, 'libportaudio.so')))
    stats = common.Stats()

    il2p = IL2P_API.IL2P_API(config=config, verbose=False)
    #args.platform = common.Platform.ANDROID
    from gps import GPS
    from OsmAndInterface import OsmAndInterface

    service_controller = ServiceController(il2p, config, GPS(), OsmAndInterface())
    il2p.service_controller = service_controller

    #call the main transceiver loop
    transceiver_func(args, service_controller, stats, il2p, config)
