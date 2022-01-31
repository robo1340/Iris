'''
Application built from a  .kv file
==================================
This shows how to implicitly use a .kv file for your application. You
should see a full screen button labelled "Hello from test.kv".
After Kivy instantiates a subclass of App, it implicitly searches for a .kv
file. The file test.kv is selected because the name of the subclass of App is
TestApp, which implies that kivy should try to load "test.kv". That file
contains a root Widget.
'''

import kivy
from kivy.config import Config
from kivy.app import App
from kivy.graphics import Color
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock
kivy.require('1.11.1')

Window.softinput_mode = "below_target" #this setting will move the text input field when the keyboard is active on an android device

import time
import numpy as np
from datetime import datetime
import threading, queue
#import random
import functools
import textwrap
import os
import sys
import logging
import pickle
import re
from collections import deque

Config.set('graphics', 'maxfps', '1')

from kivy.logger import Logger as log

from view.ui_interface import UI_Interface

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import *
import common
from common import updateConfigFile
import IL2P_API
from IL2P import IL2P_Frame_Header

class MainWindow(Screen):
    pass

class SettingsWindow(Screen):
    pass

class StatisticsWindow(Screen):
    pass

class GPSWindow(Screen):
    pass

class ChatWindow(Screen):
    pass

class WaypointWindow(Screen):
    pass

class WindowManager(ScreenManager):
    pass

def exception_suppressor(func):
    def meta_function(*args, **kwargs):
        try:
            func(*args,**kwargs)
        except BaseException:
            pass
    return meta_function

class UI_Message():
    def __init__(self, msg, background_color, header_text, time_text, message_text):
        self.msg = msg
        self.ack_key = msg.get_ack_seq()
        self.ui_time = time.time() #mark the time at which the UI element was originally created
        
        self.background_color = background_color
        self.header_text = header_text
        self.time_text = time_text
        self.message_text = message_text

class TextMessage(BoxLayout):
    pass

class ContactLabel(BoxLayout):
    pass

BLUE      = [0, 0, 1, 0.5]
RED       = [1, 0, 0, 0.5]
GREEN     = [0, 1, 0, 0.5]
BROWN     = [0.8, 0.7, 0.5, 0.5]
ORANGE    = [1,     0.6, 0, 0.5]
YELLOW    = [1, 1, 0, 0.5]
LIGHTBLUE = [0.4, 0.9, 1, 0.5]
LIGHTGREEN= [0.8, 1, 0.4, 0.5]
PURPLE    = [0.5, 0.5, 1, 0.5]
PINK      = [1, 0.5, 1, 0.5]

OSM_COLORS = [BLUE, RED, GREEN, BROWN, ORANGE, YELLOW, LIGHTBLUE, LIGHTGREEN, PURPLE, PINK]


class ui_mobileApp(App, UI_Interface):
    #def build(self):
    #    return kv
    
    ##@brief instantiate the UI
    ##@param config a dictinary object containing the parsed config file
    def __init__(self, viewController, config_file):
        
        self.viewController = viewController
        self.config_file = config_file
        
        self.header_info = AckSequenceList()
        
        self.my_callsign = ''
        self.dstCallsign = ''
        self.ackChecked = False
        self.doubleAckChecked = False
        self.enableForwarding = True
        self.autoScroll = True
        self.modulation_type = 2
        self.carrier_frequency = 1000
        self.carrier_length = 750
        
        self.gps_beacon_enable = False
        self.gps_beacon_period = 0
        
        self.include_gps_in_ack = False
        
        self.hops = 0
        
        #self.messagesLock = threading.Lock()
        #self.messages = [] # a list of message widgets
        self.messages = {} # dictionary of widgets where the key is the widget and the items are the message data
        self.my_waypoints = {}
        
        self.contact_widgets = {}
        
        
        self.main_window        = lambda : self.root.ids.main_window
        self.chat_window        = lambda : self.root.ids.chat_window
        self.settings_window    = lambda : self.root.ids.settings_window
        self.statistics_window  = lambda : self.root.ids.statistics_window
        self.gps_window         = lambda : self.root.ids.gps_window
        self.waypoint_window    = lambda : self.root.ids.waypoint_window
        
        self.gps_msg_widgets = deque(maxlen=5)
        
        self.status_update_dwell_time = 1.0 #the dwell time of status updates in seconds
        
        self.colors = {}
    
        super().__init__()
    
    ############### Callback functions called from ui.kv ###############

    def goToSettingsScreen(self):
        log.debug('transitioning to settings screen')
    
    ##@param property_widget the setable property widget
    def setable_property_changed(self, property_widget):
        if (property_widget.name == 'my_callsign'):
            self.uiSetMyCallsign(property_widget.value)
        elif (property_widget.name == 'dst_callsign'):
            self.uiSetDstCallsign(property_widget.value)
        elif (property_widget.name == 'carrier_length'):
            self.uiSetCarrierLength(property_widget.value)
    
    def uiSetMyCallsign(self, text_input_widget):
        self.my_callsign = text_input_widget.text.upper().ljust(6,' ')[0:6] #the callsign after being massaged
        text_input_widget.text = self.my_callsign
        self.viewController.send_my_callsign(self.my_callsign)
        
        self.config_file.my_callsign = self.my_callsign
        updateConfigFile(self.config_file)
        
    def uiSetDstCallsign(self, text_input_widget):
        self.dstCallsign = text_input_widget.text.upper().ljust(6,' ')[0:6] #the callsign after being massaged
        text_input_widget.text = self.dstCallsign
        
        self.config_file.dst_callsign = self.dstCallsign
        updateConfigFile(self.config_file)

    def uiSetCarrierLength(self, text_input_widget):
        newString = ''
        try:
            for char in text_input_widget.text:
                if (char.isdigit() == True):
                    newString = newString + char
            self.carrier_length = max(250,min(3000,int(newString))) #absolute max and min values are hardcoded here          
        except BaseException:
            self.carrier_length = 750 #default to this value if anything goes wrong
        #text_input_widget.text = str(self.carrier_length)
        #log.info(self.carrier_length)
        
        self.config_file.carrier_length = self.carrier_length
        updateConfigFile(self.config_file)
    
    def chat_viewed(self):
        menu_button = self.__get_child_from_base(self.main_window(), ('root_main','first_row'), 'chat_menu_button')
        menu_button.background_normal = './resources/icons/chat.png'
        
    def sendMessage(self, text_input_widget): 
        #chunks = lambda str, n : [str[i:i+n] for i in range(0, len(str), n)]  
        #messages = chunks(text_input_widget.text, 1023) #split the string the user entered into strings of max length 1023
        data = None
        if (self.ackChecked or self.doubleAckChecked): #generate an ack sequence number
            seq = np.random.randint(low=1, high=2**16-1, dtype=np.uint16)
            log.info('creating message with seq number %d' % (seq,))
        else:
            seq = np.uint16(0)
        
        dst = self.dstCallsign if (self.ackChecked or self.doubleAckChecked) else 6*' '
        
        header = IL2P_Frame_Header(src_callsign=self.my_callsign, dst_callsign=dst, \
               hops_remaining=self.hops, hops=self.hops, is_text_msg=True, is_beacon=False, \
               my_seq = seq,\
               acks=self.header_info.getAcksBool(), \
               request_ack=self.ackChecked, request_double_ack=self.doubleAckChecked, \
               payload_size=len(text_input_widget.text), \
               data=self.header_info.getAcksData())
    
        msg = MessageObject(header=header, payload_str=str(text_input_widget.text),\
                            carrier_len=self.carrier_length, priority=IL2P_API.TEXT_PRIORITY)

        self.viewController.send_txt_message(msg)
        self.addMessageToUI(msg, my_message=True)

        #clear the text input and reset the cursor
        text_input_widget.text = ''
        text_input_widget.cursor = (0,0)
            
    def sendGPSBeacon(self):
        log.info('at sendGPSBeacon()')

        self.viewController.gps_one_shot_command()
    
    def selector_pressed(self, selector, pressed_button):
        if (pressed_button.state == 'normal'):
            pressed_button.state = 'down'
            return
        #else:
        for child in selector.children:
            if (child.name != pressed_button.name):
                child.state = 'normal'
        
        if (selector.name == 'num_hops'):
            lbl = self.__get_child_from_base(self.settings_window(), ('settings_root',), 'num_hops')
            hops = int(pressed_button.name)
            hops = min(3,max(hops,0))
            self.hops = hops
            self.config_file.hops = hops
            self.viewController.update_hops(hops)
        else:
            return
        #updateConfigFile(self.config_file)
    
    def toggle_pressed(self, toggle_button):
        #print(toggle_button.name)
        #print(toggle_button.state)
        if (toggle_button.name == 'ackChecked'):
            self.ackChecked = True if (toggle_button.state == 'down') else False
        if (toggle_button.name == 'doubleAckChecked'):
            self.doubleAckChecked = True if (toggle_button.state == 'down') else False
            self.ackChecked = True if (toggle_button.state == 'down') else False
            settings = self.__get_child(self.settings_window(), 'settings_root')
            ack_button = self.__get_child(settings, 'ackChecked')
            ack_button.state = toggle_button.state 
        elif (toggle_button.name == 'enableForwarding'):
            self.enableForwarding = True if (toggle_button.state == 'down') else False
            self.viewController.send_enable_forwarding_command(self.enableForwarding)
        elif (toggle_button.name == 'enableGPS'):
            self.gps_beacon_enable = True if (toggle_button.state == 'down') else False
            self.viewController.send_gps_beacon_command(self.gps_beacon_enable,self.gps_beacon_period)
        elif (toggle_button.name == 'gpsAck'):
            self.include_gps_in_ack = True if (toggle_button.state == 'down') else False
            self.viewController.send_include_gps_in_ack(self.include_gps_in_ack)
        elif (toggle_button.name == 'enableVibration'):
            enable = True if (toggle_button.state == 'down') else False
            self.viewController.send_enable_vibration(enable)

    def button_pressed(self, button):
        if (button.name == 'force_sync_osmand'):
            self.viewController.force_sync_osmand()
        elif (button.name == 'clear_osmand_contacts'):
            self.spawn_confirm_popup('Delete Osmand Contacts?', self.viewController.clear_osmand_contacts)
        elif (button.name == 'clear_messages'):
            self.spawn_confirm_popup('Delete All Messages?' , self.clearReceivedMessages)
        elif (button.name == 'close_nobob'):
            self.spawn_confirm_popup('Close Iris?', self.shutdown_nobob)
        
    ##@param waypoint, the setable property waypoint widget
    ##@param button, the button that was pressed
    def waypoint_paste_pressed(self, waypoint, button):   
        if (button.name == 'clear'):
            waypoint.coordinates.text = ''
            if (waypoint.name in self.my_waypoints):
                self.my_waypoints.pop(waypoint.name)  #delete the entry
        elif (button.name == 'paste'):
            waypoint.coordinates.text = Clipboard.paste()
            new_coordinates = self.validate_coordinate_string(Clipboard.paste())
            if (new_coordinates is not None): #the string is valid coordinates
                self.my_waypoints[waypoint.name] = new_coordinates
                waypoint.coordinates.color = self.waypoint_window().black
                log.info(self.my_waypoints)
            else: #the string is not valid coordinates
                waypoint.coordinates.color = self.waypoint_window().red
        
        with open('./' + common.MY_WAYPOINTS_FILE, 'wb') as f:
            pickle.dump(self.my_waypoints,f) #write an empty dictionary object to the file
        
        #if this is the first time this function is being called
        #if not os.path.isfile('./' + common.MY_WAYPOINTS_FILE): 

        
    ##@brief validate a string containing gps coordinates the expected format is like so
    ## -38.7, 105.6
    ##@param coord_str the string to be validated
    ##return returns None if the coordinates could not be validated, returns a tuple of (lat,lon) on success
    def validate_coordinate_string(self, coord_str):
        result = re.match('^[-+]?([1-8]?\d\.\d+?|90\.0+?)[ ,]*\s*[-+]?(180\.0+?|1[0-7]\d|[1-9]?\d\.\d+?)$', coord_str)
        if (result is None):
            return None
        if (len(result.groups()) != 2):
            return None
        else:
            try:
                return (result.groups()[0], result.groups()[1])
            except BaseException:
                return None
    
    def spinner_pressed(self, spinner):
        if (spinner.name == 'gps_beacon_period'):
            #update the property containing current beacon period
            property = self.__get_child_from_base(self.gps_window(), ('root_gps',), 'current_gps_beacon_period')
            property.value_text = spinner.text
            self.gps_beacon_period = int(spinner.text)
            self.viewController.send_gps_beacon_command(self.gps_beacon_enable,self.gps_beacon_period)

    def spawn_confirm_popup(self, message, yes_func):
        self.box_popup = BoxLayout(orientation = 'vertical')
        self.popup_exit = Popup(title = 'Are you sure?',content = self.box_popup,size_hint = (0.5, 0.5),auto_dismiss = True)
        
        def yes_callback(*args):
            yes_func()
            self.popup_exit.dismiss()
        
        self.box_popup.add_widget(Label(text = message))
        self.box_popup.add_widget(Button(text = "Yes", on_press = yes_callback ))
        self.box_popup.add_widget(Button(text = "No", on_press = self.popup_exit.dismiss)) #size_hint=(0.215, 0.075)

        self.popup_exit.open()
            
    
    ############## input functions implementing UI_Interface #################
    
    ##@brief the method called by the viewController that will schedule a status update, after the
    ##       dwell time for the previous status update has ellapsed
    ##@param status an integer value that maps to the new status to be added to the queue
    def updateStatusIndicator(self, *largs):
        if os.path.isfile('./' + common.STATUS_IND_FILE):
            if ((time.time() - os.path.getmtime('./' + common.STATUS_IND_FILE)) < 0.2): #if only modified recently
                with open('./' + common.STATUS_IND_FILE, 'rb') as f:
                    try:
                        status = pickle.load(f)

                        if (status == common.SQUELCH_OPEN):
                            name = 'squelch'
                        elif (status == common.CARRIER_DETECTED):
                            name = 'receiver'
                        elif (status == common.MESSAGE_RECEIVED):
                            name = 'receiver_success'
                        elif (status == common.TRANSMITTING):
                            name = 'transmitter'
                        else:
                            return

                        mgif = self.__get_child_from_base(self.main_window(),('root_main','first_row','status_indicators'), name)
                        mgif._coreimage.anim_reset(True)
                        mgif.anim_delay = 0.1

                        cgif = self.__get_child_from_base(self.chat_window(),('root_chat','first_row','status_indicators'), name)
                        cgif._coreimage.anim_reset(True)
                        cgif.anim_delay = 0.1
                    except BaseException:
                        pass
    
    def load_messages_from_file(self):
        ui_messages = common.load_message_file()
        #self.messages = common.load_message_file()
        message_container = self.__get_child_from_base(self.chat_window(),('root_chat','second_row','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(self.chat_window(), ('root_chat','second_row'), 'scroll_bar')
        
        for ui_message in ui_messages:
            widget = TextMessage() #create the new widget
            widget.background_color = self.colors[ui_message.background_color]
            widget.header_text = ui_message.header_text
            widget.time_text = ui_message.time_text
            widget.message_text = ui_message.message_text
            self.messages[widget] = ui_message
            message_container.add_widget(widget)
            
        #if (self.autoScroll == True):
        #    scroll_bar.scroll_to(txt_msg_widget)
            
    ##@brief add a new message label to the main scroll panel on the gui
    ##@param msg A TextMessageObject containing the received message
    ##@param my_message, set to True when the method is coming from the local UI, set to False when the message is being received from the service
    def addMessageToUI(self, msg, my_message=False, *largs):
        chat_window = self.chat_window()
        message_container = self.__get_child_from_base(chat_window,('root_chat','second_row','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(chat_window, ('root_chat','second_row'), 'scroll_bar')
        
        if ((not my_message) and (msg.header.src_callsign == self.my_callsign)): #don't display message received from the audio loopback
            return
        
        if (self.root.current != "chat") and (not my_message):
            menu_button = self.__get_child_from_base(self.main_window(), ('root_main','first_row'), 'chat_menu_button')
            menu_button.background_normal = './resources/icons/chat_pending.png'          
        
        #get the strings the widget will be filled with
        if (msg.header.dst_callsign == 6*' '):
            header_text = msg.header.src_callsign
        else:
            header_text = "%s to %s" % (msg.header.src_callsign, msg.header.dst_callsign)
        
        time_text = msg.time_str
        message_text = msg.payload_str.rstrip('\n')
        
        background_color = chat_window.text_msg_color

        if (msg.header.dst_callsign == self.my_callsign): #if the message was addressed to me
            background_color = chat_window.text_msg_at_color
            message_text = '@' + self.my_callsign + ' ' + message_text
            
        if ((my_message == True) and(msg.header.src_callsign == self.my_callsign)): #if the message was sent by me
            
            if (msg.header.request_ack == True):
                background_color = chat_window.text_msg_color_ack_pending
            else:
                background_color = chat_window.text_msg_color_no_ack_expect
            sent_time_str = "| %s" % (datetime.now().strftime("%H:%M:%S"),)
            ack_time_str = ' | Ack Pending' if (msg.header.request_ack == True) else ''
            time_text = sent_time_str + ack_time_str
        
        txt_msg_widget = TextMessage() #create the new widget
        txt_msg_widget.background_color = background_color
        txt_msg_widget.header_text = header_text
        txt_msg_widget.time_text = time_text
        txt_msg_widget.message_text = message_text
        message_container.add_widget(txt_msg_widget)
        
        background_color_ind = [i for i,x in enumerate(self.colors) if x == background_color][0]
        ui_message = UI_Message(msg, background_color_ind, header_text, time_text, message_text)
        self.messages[txt_msg_widget] = ui_message
        
        common.update_message_file(list(self.messages.values()))

        if (self.autoScroll == True):
            scroll_bar.scroll_to(txt_msg_widget)
        
    ##@brief look through the current messages displayed on the ui and update any that have an ack_key matching the ack_key passed in
    ##@ack_key, the sequence number for the ack message
    def addAckToUI(self, ack_key, *largs):
        current = time.time()
        for widget, msg in self.messages.items():
            if ((current - msg.ui_time) > 3600): #don't bother looking for acks in messages more than an hour old
                continue
            if (msg.ack_key is None):
                continue
            if (msg.ack_key == ack_key):
                widget.time_text = "Acked at %s" % (datetime.now().strftime("%H:%M:%S"),)
                widget.background_color = self.chat_window().text_msg_color_ack_received
                msg.background_color = [i for i,x in enumerate(self.colors) if x == widget.background_color][0]
                msg.time_text = widget.time_text
        common.update_message_file(list(self.messages.values()))

    ##@brief look through the current messages displayed on the ui and update any that have an ack_key matching the ack_key passed in
    ##@ack_key, a sequence number forming the ack this message expects
    ##@remaining_retries, the number of times this message will be re-transmitted if no ack is received
    def updateRetryCount(self, ack_key, remaining_retries, *largs):
        for widget, msg in self.messages.items():
            if (msg.ack_key is None):
                continue
            if (msg.ack_key == ack_key):
                if (remaining_retries == -1): #mark this message as having received no acknowledgments before timeout
                    widget.time_text = ' | No Ack Received'
                else: #update the remaining retries value
                    widget.time_text = '| %s | %d retries left' % (datetime.now().strftime("%H:%M:%S"), remaining_retries)
                msg.time_text = widget.time_text
        common.update_message_file(list(self.messages.values()))
    
    def updateHeaderInfo(self, info, *largs):
        self.header_info = info
    
    def updateStatistics(self, *largs):
        if os.path.isfile('./' + common.STATISTICS_FILE):
            with open('./' + common.STATISTICS_FILE, 'rb') as f:
                try:
                    stats = pickle.load(f)
                    self.__update_property('tx_success_cnt',str(stats.txs))
                    self.__update_property('tx_failure_cnt',str(stats.txf))
                    self.__update_property('rx_success_cnt',str(stats.rxs))
                    self.__update_property('rx_failure_cnt',str(stats.rxf))
                except BaseException:
                    pass
        
    def __update_property(self,property_name,new_val):
        property = self.__get_child_from_base(self.statistics_window(), ('root_stats',), property_name)
        property.value_text = new_val
    
    def clearReceivedMessages(self):
        #clear all messages from the UI first
        message_container = self.__get_child_from_base(self.chat_window(),('root_chat','second_row','scroll_bar'), 'message_container')
        
        for widget in self.messages.keys():
            message_container.remove_widget(widget)
        
        #now clear messages from disk
        self.messages = {}
        common.update_message_file(list(self.messages.values()))
        
        return True ###### Note: this isn't really implemented but isn't needed at the moment
    
    def isAckChecked(self):
        return self.ackChecked
        
    def isGPSTxOneShotChecked(self):
        return False
        
    def isGPSTxChecked(self):
        return self.gps_beacon_enable
    
    def getGPSBeaconPeriod(self):
        return self.gps_beacon_period
    
    #@exception_suppressor
    def update_my_displayed_location(self, gps_dict, *largs):
        self.__update_gps_property('latitude' ,str(gps_dict['lat']))
        self.__update_gps_property('longitude',str(gps_dict['lon']))
        self.__update_gps_property('altitude' ,str(round(gps_dict['altitude'],2)))
            
    def __update_gps_property(self,property_name,new_val):
        property = self.__get_child_from_base(self.gps_window(), ('root_gps',), property_name)
        property.value_text = new_val
        
    def addGPSMessageToUI(self, gps_msg, *largs):
        gps_window = self.gps_window()
        message_container = self.__get_child_from_base(gps_window,('root_gps','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(gps_window, ('root_gps',), 'scroll_bar')
        
        gps_msg_widget = TextMessage() #create the new widget
        
        #get the strings the widget will be filled with
        header_text = ('{0:s}').format(gps_msg.src_callsign)
        time_text = ('{0:s}').format(gps_msg.time_str)
        message_text = gps_msg.getInfoString()
        
        gps_msg_widget.background_color = self.chat_window().text_msg_color
        
        gps_msg_widget.header_text = header_text
        gps_msg_widget.time_text = time_text
        gps_msg_widget.message_text = message_text
        message_container.add_widget(gps_msg_widget)
        self.gps_msg_widgets.append(gps_msg_widget)
        
        if (len(self.gps_msg_widgets) == self.gps_msg_widgets.maxlen):
            to_delete = self.gps_msg_widgets.popleft()
            message_container.remove_widget(to_delete)
        
        if (self.autoScroll == True):
            scroll_bar.scroll_to(gps_msg_widget)
    
    def addNewGPSContactToUI(self, gps_msg, *largs):
        main_window = self.main_window()
        
        message_container = self.__get_child_from_base(main_window,('root_main','second_row','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(main_window, ('root_main','second_row'), 'scroll_bar')
        
        contact_widget = ContactLabel() #create the new widget
        
        contact_widget.callsign_text = gps_msg.src_callsign
        contact_widget.time_text     = ('{0:s}').format(gps_msg.time_str)
        
        contact_widget.background_color = OSM_COLORS[ (len(self.contact_widgets) % len(OSM_COLORS)) ]
        
        message_container.add_widget(contact_widget) #add the widget to the UI
        self.contact_widgets[gps_msg.src_callsign] = contact_widget #add the widget to a dictionary, where the key is the callsign of the gps message
    
    def updateGPSContact(self, gps_msg, *largs):
        if gps_msg.src_callsign in self.contact_widgets:
            widget = self.contact_widgets[gps_msg.src_callsign]
            widget.time_text = ('{0:s}').format(gps_msg.time_str)
            
    def notifyGPSLockAchieved(self, *largs):
        gps_lock_label = self.__get_child_from_base(self.gps_window(),('root_gps',), 'gps_lock_label')
        gps_lock_label.text = "GPS Lock Achieved"
        
    ##@brief update the audio signal strength indicator on the main page of the app
    ##@param signal_strength, floating point value indicating the signal strength, should be between 0.05 and 0.6
    #@exception_suppressor
    def update_signal_strength(self, *largs):
        try:
            if os.path.isfile('./' + common.SIGNAL_STRENGTH_FILE):
                with open('./' + common.SIGNAL_STRENGTH_FILE, 'rb') as f:
                    signal_strength = pickle.load(f)

                    main_window = self.main_window()
                    signal_indicator = self.__get_child_from_base(self.main_window(), ('root_main', 'first_row'), 'signal_strength_indicator')


                    main_window.signal_strength_color = main_window.white

                    angle_deg = signal_strength*4
                    radius = signal_indicator.height/2
                    main_window.guage_x = -int(radius * np.cos(np.pi/180 * angle_deg))
                    main_window.guage_y = int(radius * np.sin(np.pi/180 * angle_deg))

                    main_window.signal_strength = ''
        except EOFError:
            pass
        except BaseException:
            log.error('error occurred in update_signal_strength()')
        
    ################### private functions ##############################
    
    def __apply_config(self, config):
        settings = self.__get_child(self.settings_window(), 'settings_root')
        
        ack_widget = self.__get_child(settings, 'ackChecked')
        self.ackChecked = config.ackChecked
        ack_widget.state = 'down' if self.ackChecked else 'normal'
        
        enable_widget = self.__get_child(settings, 'enableForwarding')
        self.enableForwarding = config.enableForwarding
        enable_widget.state = 'down' if self.enableForwarding else 'normal'
        
        vibrate_widget = self.__get_child(settings, 'enableVibration')
        vibrate_widget.state = 'down' if config.enable_vibration else 'normal'
        
        #scroll_widget = self.__get_child(settings, 'autoScroll')
        self.autoScroll = config.autoScroll
        #scroll_widget.state = 'down' if self.autoScroll else 'normal'

        dst_callsign_widget = self.__get_child(settings, 'dst_callsign')
        dst_callsign_widget.text = config.dst_callsign
        self.dstCallsign = config.dst_callsign
        
        my_callsign_widget = self.__get_child(settings,'my_callsign')
        my_callsign_widget.text = config.my_callsign
        self.my_callsign = config.my_callsign 
        
        carrier_length_widget = self.__get_child(settings,'carrier_length')
        carrier_length_widget.text = str(config.carrier_length)
        self.carrier_length = config.carrier_length
        
        self.modulation_type = config.Npoints
        self.carrier_frequency = config.frequencies[0]
        
        hops_selector = self.__get_child(settings, 'num_hops')
        self.__get_child(hops_selector, '0').state = 'down'
        
        gps = self.__get_child(self.gps_window(), 'root_gps')
        
        gps_enable = self.__get_child(gps, 'enableGPS')
        self.gps_beacon_enable = config.gps_beacon_enable
        gps_enable.state = 'down' if self.gps_beacon_enable else 'normal'
        
        gps_period = self.__get_child(gps,'gps_beacon_period')
        self.gps_beacon_period = config.gps_beacon_period
        gps_period.text = str(self.gps_beacon_period)
        
        waypoint = self.__get_child(self.waypoint_window(), 'root_waypoint')
        waypoint_period = self.__get_child(waypoint,'waypoint_period')
        self.waypoint_beacon_period = config.waypoint_beacon_period
        waypoint_period.text = str(self.waypoint_beacon_period)

    def __get_child(self, widget, name):
        for child in widget.children:
            if (child.name == name):
                return child
        
    ##@brief starting from the root widget, retrieve a widget using the names of all of its parent widgets
    ##@brief base reference to the base widget that contains the desired widget
    ##@param names a tuple of strings naming the children of the base widget to get to the desired widget
    ##@param desired_name string, the name of the widget to be returned
    ##@return returns the desired widget if it is found, returns None otherwise
    def __get_child_from_base(self, base, names, desired_name):
        first_iter = True
        widget = None
        try:
            for name in names:
                if (first_iter == True):
                    widget = self.__get_child(base,name)
                    if (widget is None):
                        log.debug('NONE')
                    first_iter = False
                else:
                    widget = self.__get_child(widget,name)
            widget = self.__get_child(widget,desired_name)
        except BaseException:
            log.error('ERROR!: a widget could not be found')
            return None
        return widget        

    ################# override functions #########################
    
    #callback is called when application is started
    def on_start(self, **kwargs):
        self.__apply_config(self.config_file)
        
        chat_window = self.chat_window()
        self.colors = [chat_window.text_msg_color,
                       chat_window.text_msg_at_color,
                       chat_window.text_msg_color_ack_pending,
                       chat_window.text_msg_color_ack_received,
                       chat_window.text_msg_color_no_ack_expect
                      ]
        
        self.load_messages_from_file() #load any pre-existing messages
        
        Clock.schedule_interval(self.updateStatusIndicator, 0.1)
        Clock.schedule_interval(self.updateStatistics, 1.0)
        Clock.schedule_interval(self.update_signal_strength, 0.1)
   
    #gracefully shut everything down when the user exits
    
    def shutdown_nobob(self):
        log.info('stop()')
        self.viewController.service_stop_command() # send a message to stop the service threads
        time.sleep(0.75)
        self.viewController.stop() ##ui has stopped (the user likely clicked exit), stop the view Controller
        App.get_running_app().stop()
   