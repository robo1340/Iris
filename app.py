import threading
import time
import queue
import logging
import sys
import time
import argparse
import configparser

import common
from transceiver import chat_transceiver_func
from view.view_controller import *
import config
import audio

import IL2P_API

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

my_callsign = ''
dst_callsign = ''
ack_checked_initial = 0

def parseCommandLineArguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", help="pass in the configuration file")
    parser.add_argument('-t','--tkinter', action="store_true", help='set this flag when you want to use the old tkinter UI')
    commandline_args = parser.parse_args()
    #print (commandline_args.config)
    return commandline_args

def parseConfigFile(config_file_path):
    config = configparser.ConfigParser()
    config.read(config_file_path)
    return config

def verify_ini_config(ini_config):
    toReturn = True #assume the ini file will be ok
    
    properties = ['my_callsign', 'dst_callsign', 'ack_retries', 'ack_timeout', 'tx_cooldown', 
                  'rx_cooldown', 'rx_timeout', 'ack', 'clear', 'scroll', 'master_timeout', 
                  'Fs', 'Npoints', 'num_f', 'f_low', 'f_high', 'min_wait', 'max_wait']
    
    for p in properties:
        if not (p in ini_config['MAIN']):
            toReturn = False
            print ('ERROR: %s property not found in .ini config file!' % (p))
            
    return toReturn

if __name__ == "__main__":

    args = parseCommandLineArguments()
    use_tkinter = args.tkinter
    ini_config = parseConfigFile(args.config_file)
    if not verify_ini_config(ini_config):
        raise Exception('Error: Not all needed values were found in the .ini configuration file')
        
    interface = audio.Interface(config)
    
    #select an audio library
    if ((sys.platform == 'win32') and (sys.maxsize > 2**32)): #true if this is a windows 64 bit system
        interface.load('dll/libportaudio-2.dll')
    elif ((sys.platform == 'win32') and not (sys.maxsize > 2**32)): #true if this is a windows 32 bit system
        interface.load('dll/portaudio32.dll')
    #elif (this is linux):
    #    interface.load('libportaudio.so')
    else:
        print(sys.platform)
        raise Exception('Error: This system is not recognized')
        
    args = Args(interface=interface)
    stats = Stats()
    _config_log(0,False)

    msg_send_queue = queue.Queue(25)
    ack_output_queue = queue.Queue(25)
    msg_output_queue = queue.Queue(25)
    
    il2p = IL2P_API.IL2P_API(ini_config=ini_config, verbose=False, msg_output_queue=msg_output_queue, ack_output_queue=ack_output_queue, msg_send_queue=msg_send_queue)
    
    if (use_tkinter == False):
        import view.ui_kivy
        ui = view.ui_kivy.UiApp(il2p, ini_config)  
    elif (use_tkinter == True):   
        import view.ui_tkinter
        ui = view.ui_tkinter.GUI(il2p, ini_config)

    args.ui = ui
    
    transceiver_thread = common.StoppableThread(target=chat_transceiver_func, args=(args, stats, il2p, ini_config))
    ui_thread = common.StoppableThread(target = view_controller_func, args=(ui, il2p, ini_config))
    
    transceiver_thread.start()
    ui_thread.start()
    
    #ui.run() #this call is blocking
    ui.run()
    
    ##ui has stopped (the user likely clicked exit), stop all the other threads
    ui_thread.stop()
    transceiver_thread.stop()        
    