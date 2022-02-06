import threading
import time
import queue
import logging
import sys
import time
import argparse
import os
import pickle

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

if __name__ == "__main__":
    log.info('Start of Main Application')

    #device_type = common.getPlatform() #determine what platform this is
    #if (device_type == common.Platform.ANDROID):
    
    from android.permissions import request_permissions, Permission
    from kivy.utils import platform
    request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.RECORD_AUDIO, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.INTERNET, Permission.VIBRATE, Permission.MODIFY_AUDIO_SETTINGS, Permission.FOREGROUND_SERVICE])

    if os.path.isfile('./' + common.CONFIG_FILE):
        with open(common.CONFIG_FILE, 'rb') as f:
            config = pickle.load(f)
    else:
        config = config.Configuration(Fs=8000, Npoints=2, frequencies=[2000])
        common.updateConfigFile(config)

    viewController = ViewController(config)
    import view.ui_mobile_kivy
    ui = view.ui_mobile_kivy.ui_mobileApp(viewController, config)
    viewController.ui = ui

    time.sleep(1.0) #wait a bit

    #from jnius import autoclass
    #service = autoclass('com.projectx.nobob.ServiceService')
    #mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
    #service.start(mActivity, 'arg')

    import android
    android.start_service(title='Iris Service',description='Iris Radio Service',arg='arg')

    #from inspect import getmembers, isfunction
    #log.info('------------------------------------')
    #help(android)
    #log.info(getmembers(android, isfunction))

    ui.run() #blocking call until user exits the app
    #android.stop_service(title='NoBoB Service')
    log.info('UI has exited!')

    