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
    log.info('Start of Main Application')

    device_type = common.getPlatform() #determine what platform this is

    if (device_type == common.Platform.ANDROID):
        from android.permissions import request_permissions, Permission
        from kivy.utils import platform
        request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.RECORD_AUDIO, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET, Permission.VIBRATE, Permission.MODIFY_AUDIO_SETTINGS, Permission.FOREGROUND_SERVICE])

        ini_config = common.parseConfigFile(common.CONFIG_FILE_NAME)
        #print(ini_config.sections())
        if not common.verify_ini_config(ini_config):
            raise Exception('Error: Not all needed values were found in the .ini configuration file')

        viewController = ViewController()
        import view.ui_mobile_kivy
        ui = view.ui_mobile_kivy.ui_mobileApp(viewController, ini_config)
        viewController.ui = ui

        #from jnius import autoclass
        #service = autoclass('com.projectx.nobob.ServiceService')
        #mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
        #service.start(mActivity, 'arg')
        
        import android
        android.start_service(title='NoBoB Service',description='NoBoB Radio Service',arg='arg')
        
        #from inspect import getmembers, isfunction
        #log.info('------------------------------------')
        #help(android)
        #log.info(getmembers(android, isfunction))

        ui.run() #blocking call until user exits the app
        #android.stop_service(title='NoBoB Service')
        log.info('UI has exited!')

    