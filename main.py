import threading
import time
import queue
import logging
import sys
import time
import argparse
import configparser

import common
from view.view_controller import ViewController
import config
import audio
import ctypes
from kivy.logger import Logger as log
#log = logging.getLogger('__name__')

import IL2P_API

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

if __name__ == "__main__":

    device_type = common.getPlatform() #determine what platform this is
    
    log.info('Start of Main Application')

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
        service = android.start_service(title='NoBoB Service', description='NoBoB Transceiver Running', arg='')

        ui.run() #blocking call
        
        print('yo')
        viewController.service_stop_command() #stop the service threads
        
        
        viewController.stop() ##ui has stopped (the user likely clicked exit), stop the view Controller   
    