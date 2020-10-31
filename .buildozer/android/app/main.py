import threading
import time
import queue
import logging
import sys
import time
import argparse
import configparser

import common
from view.view_controller import *
from view.view_controller2 import ViewController
import config
import audio
import ctypes
from kivy.logger import Logger

import IL2P_API

log = logging.getLogger('__name__')

my_callsign = ''
dst_callsign = ''
ack_checked_initial = 0

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

def parseCommandLineArguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", help="pass in the configuration file")
    parser.add_argument('-t','--tkinter', action="store_true", help='set this flag when you want to use the old tkinter UI')
    commandline_args = parser.parse_args()
    #print (commandline_args.config)
    return commandline_args

if __name__ == "__main__":

    device_type = common.getPlatform() #determine what platform this is
    
    _config_log(1,False) #configure the logs
    Logger.info('Start of Main Application')
    print('main')

###################################################################        
####################### Android Device ############################
###################################################################    
    if (device_type == common.Platform.ANDROID):
        from android.permissions import request_permissions, Permission
        from kivy.utils import platform
        request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.RECORD_AUDIO, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET])
        
        ini_config = common.parseConfigFile(common.CONFIG_FILE_NAME)
        #print(ini_config.sections())
        if not common.verify_ini_config(ini_config):
            raise Exception('Error: Not all needed values were found in the .ini configuration file')

        viewController = ViewController()
        import view.ui_mobile_kivy
        ui = view.ui_mobile_kivy.ui_mobileApp(viewController, ini_config)
        viewController.ui = ui
        
        ##start the service now
        import android
        android.start_service(title='NoBoB Service', description='service description', arg='')

        ui.run() #blocking call
        #Main program running now
        viewController.stop() ##ui has stopped (the user likely clicked exit), stop the view Controller
    
###################################################################        
################### Non-Android Device ############################
###################################################################    
    else:
        args = parseCommandLineArguments()
        use_tkinter = args.tkinter
        #print(args.config_file)
        common.CONFIG_FILE_NAME = args.config_file
        ini_config = parseConfigFile(common.CONFIG_FILE_NAME)
        
        if not verify_ini_config(ini_config):
            raise Exception('Error: Not all needed values were found in the .ini configuration file')
           
        #create a config object from the ini_config settings
        Fs = int(ini_config['MAIN']['Fs'])
        Npoints = int(ini_config['MAIN']['Npoints'])
        cf = int(ini_config['MAIN']['carrier_frequency'])
        #config = config.Configuration(Fs=8e3, Npoints=2, frequencies=[1000])
        config = config.Configuration(Fs=Fs, Npoints=Npoints, frequencies=[cf])
           
        interface = audio.Interface(config)
        
        #select an audio library
        if (device_type == common.Platform.WIN64): #true if this is a windows 64 bit system
            interface.load('dll/libportaudio-2.dll')
        elif (device_type == common.Platform.WIN32): #true if this is a windows 32 bit system
            interface.load('dll/portaudio32.dll')
        elif (device_type == common.Platform.LINUX):
            interface.load('libportaudio.so')
        else:
            raise Exception('Error: This system is not recognized')


        args = Args(interface=interface)
        stats = Stats()

        msg_send_queue = queue.Queue(25)
        ack_output_queue = queue.Queue(25)
        msg_output_queue = queue.Queue(25)
        
        il2p = IL2P_API.IL2P_API(ini_config=ini_config, verbose=False, msg_output_queue=msg_output_queue, ack_output_queue=ack_output_queue, msg_send_queue=msg_send_queue)
        
        if (use_tkinter == False):
            import view.ui_mobile_kivy
            ui = view.ui_mobile_kivy.ui_mobileApp(il2p, ini_config)
            #import view.ui_kivy
            #ui = view.ui_kivy.UiApp(il2p, ini_config)  
        elif (use_tkinter == True):   
            import view.ui_tkinter
            ui = view.ui_tkinter.GUI(il2p, ini_config)

        args.ui = ui
        args.platform = device_type
        
        transceiver_thread = common.StoppableThread(target=chat_transceiver_func, args=(args, stats, il2p, ini_config, config))
        ui_thread = common.StoppableThread(target = view_controller_func, args=(ui, il2p, ini_config))
        
        transceiver_thread.start()
        ui_thread.start()
        
        ui.run() #this call is blocking
        
        ##ui has stopped (the user likely clicked exit), stop all the other threads
        ui_thread.stop()
        transceiver_thread.stop()        
    