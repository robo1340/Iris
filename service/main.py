#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
#import argparse

import sys
import itertools
import logging
import functools
import os
import io
import numpy as np
import threading
import time
import queue
import wave

sys.path.insert(0,'..') #need to insert parent path to import something from messages

from func_timeout import func_set_timeout, FunctionTimedOut

import pkg_resources
import async_reader
import audio
import common
from common import Status
import send as _send
import recv as _recv
import stream
import detect
import sampling
import exceptions
import ctypes

import config

import IL2P_API
from transceiver import transceiver_func
from service_controller import ServiceController

master_timeout = 20 #sets the timeout for the last line of defense when the program is stuck
tx_cooldown = 1 #cooldown period after the sending in seconds, the program may not transmit for this period of time after transmitting a frame
rx_cooldown = 0.5 #cooldown period after receiving in seconds, the program may not receive or transmit for this period of time after receiving a frame

# Python 3 has `buffer` attribute for byte-based I/O
_stdin = getattr(sys.stdin, 'buffer', sys.stdin)
_stdout = getattr(sys.stdout, 'buffer', sys.stdout)

log = logging.getLogger('__name__')

## @brief simple contain to put arguments used throughout the program in 
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
    
    time.sleep(1) #put a slight delay in when the service starts, so that the UI will be started before the service
    
    print('start of service')
    
    #from jnius import autoclass
    #PythonService = autoclass('org.kivy.android.PythonService')
    #PythonService.mService.setAutoRestartService(True)
    
    #from android.permissions import request_permissions, Permission
    #from kivy.utils import platform
    #request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.RECORD_AUDIO, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET])

    cwd = os.path.dirname(os.path.abspath(__file__)) #get the current working directory

    ctypes.CDLL(os.path.join(cwd, 'libgnustl_shared.so'))
    ctypes.CDLL(os.path.join(cwd, 'libportaudio.so'))
    print('libportaudio loaded')

    #args = parseCommandLineArguments()
    ini_config = common.parseConfigFile(common.CONFIG_FILE_NAME)
    if not common.verify_ini_config(ini_config):
        raise Exception('Error: Not all needed values were found in the .ini configuration file')

    #create a config object from the ini_config settings
    Fs = int(ini_config['MAIN']['Fs'])
    Npoints = int(ini_config['MAIN']['Npoints'])
    cf = int(ini_config['MAIN']['carrier_frequency'])
    config = config.Configuration(Fs=Fs, Npoints=Npoints, frequencies=[cf])

    args = Args(interface=audio.Interface(config).load(os.path.join(cwd, 'libportaudio.so')))
    stats = common.Stats()
    msg_send_queue = queue.Queue(50)
    #ack_output_queue = queue.Queue(25)
    #msg_output_queue = queue.Queue(25)

    il2p = IL2P_API.IL2P_API(ini_config=ini_config, verbose=False, msg_send_queue=msg_send_queue)
    args.platform = common.Platform.ANDROID
    from android_only.gps import GPS
    from android_only.OsmAndInterface import OsmAndInterface

    service_controller = ServiceController(il2p, ini_config, GPS(), OsmAndInterface())
    il2p.service_controller = service_controller
    transceiver_thread = common.StoppableThread(target=transceiver_func, args=(args, service_controller, stats, il2p, ini_config, config))
    
    transceiver_thread.start()

    while(True):
        time.sleep(10)

    