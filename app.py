import threading
import time
import queue
import logging
import sys
import time

import common
from transceiver import chat_transceiver_func
from view.view_controller import *
import view.ui
import config
import audio

log = logging.getLogger('__name__')

config = config.main_config

def _config_log(verbose,quiet):
    if verbose == 0:
        level, fmt = 'INFO', '%(message)s'
    elif verbose == 1:
        level, fmt = 'DEBUG', '%(message)s'
    elif verbose >= 2:
        level, fmt = ('DEBUG', '%(asctime)s %(levelname)-10s %(message)-100s %(filename)s:%(lineno)d')
    if quiet:
        level, fmt = 'WARNING', '%(message)s'
    logging.basicConfig(level=level, format=fmt)

## @brief simple contain to put arguments used throughout the program in 
class Args():
    def __init__(self, interface=None):
        self.recv_src = None
        self.recv_dst = None
        self.ui = None
        self.interface = interface
        
        self.sender_src = None
        self.sender_dst = None
        
        self.input = None
        self.output = None

## @brief simple container to put relevant statics and log items as the program runs
class Stats():
    def __init__(self):
        self.txs = 0 ##tx success count
        self.txf = 0 ##rx failure count
        self.rxs = 0 ##rx success count
        self.rxf = 0 ##rx failure count

if __name__ == "__main__":

    interface = audio.Interface(config)
    
    #select an audio library
    if ((sys.platform == 'win32') and (sys.maxsize > 2**32)): #true if this is a windows 64 bit system
        interface.load('dll/libportaudio-2.dll')
    elif ((sys.platform == 'win32') and not (sys.maxsize > 2**32)): #true if this is a windows 32 bit system
        interface.load('dll/portaudio32.dll')
    else:
        raise Exception('Error: This system is not recognized')
        
    args = Args(interface=interface)
    stats = Stats()
    _config_log(0,False)

    send_queue = queue.Queue(10)
    recv_queue = queue.Queue(10)
    
    ui = view.ui.GUI(send_queue)
    args.ui = ui
    
    transceiver_thread = common.StoppableThread(target=chat_transceiver_func, args=(args, stats, send_queue, recv_queue))
    ui_thread = common.StoppableThread(target = view_controller_func, args=(ui, send_queue, recv_queue))
    
    transceiver_thread.start()
    ui_thread.start()
    
    ui.init_ui() #this call is blocking
    
    ##ui has stopped (the user likely clicked exit), stop all the other threads
    ui_thread.stop()
    transceiver_thread.stop()        
    