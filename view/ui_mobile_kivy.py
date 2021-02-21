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
import plyer
from kivy.config import Config
from kivy.app import App
from kivy.graphics import Color
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.stacklayout import StackLayout
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
kivy.require('1.11.1')

Window.softinput_mode = "below_target" #this setting will move the text input field when the keyboard is active on an android device

import time
from datetime import datetime
import threading, queue
#import random
import functools
import textwrap
import sys
import logging
from collections import deque

#Config.set('graphics', 'resizable', False)
#Config.set('graphics', 'width', '1024')
#Config.set('graphics', 'height', '650')
Config.set('graphics', 'maxfps', '1')

from kivy.logger import Logger as log

from view.ui_interface import UI_Interface

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject
from common import Status
from common import updateConfigFile

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

class WindowManager(ScreenManager):
    pass
    
#kv = Builder.load_file('./view/ui_mobile.kv')

def exception_suppressor(func):
    def meta_function(*args, **kwargs):
        try:
            func(*args,**kwargs)
        except BaseException:
            pass
    return meta_function
        
class UI_Message():
    def __init__(self, msg, widget):
        self.ack_key = (msg.src_callsign,msg.dst_callsign,msg.seq_num) if (msg.expectAck == True) else ('','',0)
        self.widget = widget

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
    ##@param ini_config a dictinary object containing the parsed config.ini file
    def __init__(self, viewController, ini_config):
        Window.bind(on_key_down=self._on_keyboard_down)
        Window.bind(on_key_up=self._on_keyboard_up)
        
        self.viewController = viewController
        self.ini_config = ini_config
        
        self.my_callsign = ''
        self.dstCallsign = ''
        self.ackChecked = False
        self.clearOnSend = False
        self.autoScroll = False
        self.modulation_type = 2
        self.carrier_frequency = 1000
        self.carrier_length = 750
        
        self.gps_beacon_enable = False
        self.gps_beacon_period = 0
        
        self.messagesLock = threading.Lock()
        self.messages = []
        
        self.contact_widgets = {}
        
        #self.main_window = lambda : self.__get_child(self.root, 'main')
        self.main_window        = lambda : self.root.ids.main_window
        self.chat_window        = lambda : self.root.ids.chat_window
        self.settings_window    = lambda : self.root.ids.settings_window
        self.statistics_window  = lambda : self.root.ids.statistics_window
        self.gps_window         = lambda : self.root.ids.gps_window
        
        self.gps_msg_widgets = deque(maxlen=5)
        
        self.status_updates = queue.Queue(maxsize=50) #a queue used to store status updates
        self.last_status_update_time = time.time() #the time of the last status update
        self.status_update_dwell_time = 0.5 #the dwell time of status updates in seconds
        self.statusIndicatorLock = threading.Lock() #lock used to protect the status indicator ui elements
        self.has_ellapsed = lambda start, duration : ((time.time() - start) > duration)
    
        super().__init__()
        
    ############### Callback functions called from ui.kv ###############
    
    def goToSettingsScreen(self):
        log.debug('transitioning to settings screen')
    
    def uiSetMyCallsign(self, text_input_widget):
        self.my_callsign = text_input_widget.text.upper().ljust(6,' ')[0:6] #the callsign after being massaged
        text_input_widget.text = self.my_callsign
        self.viewController.send_my_callsign(self.my_callsign)
        
        self.ini_config['MAIN']['my_callsign'] = self.my_callsign
        updateConfigFile(self.ini_config)
        
    def uiSetDstCallsign(self, text_input_widget):
        self.dstCallsign = text_input_widget.text.upper().ljust(6,' ')[0:6] #the callsign after being massaged
        text_input_widget.text = self.dstCallsign
        
        self.ini_config['MAIN']['dst_callsign'] = self.dstCallsign
        updateConfigFile(self.ini_config)

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
        self.ini_config['MAIN']['carrier_length'] = str(self.carrier_length)
        updateConfigFile(self.ini_config)
    
    def sendMessage(self, text_input_widget): 
        chunks = lambda str, n : [str[i:i+n] for i in range(0, len(str), n)]  
 
        messages = chunks(text_input_widget.text, 1023) #split the string the user entered into strings of max length 1023
        src = self.my_callsign
        dst = self.dstCallsign
        ack = self.ackChecked
        #print('ackChecked ' + str(ack))
        for msg_str in messages:
            msg = TextMessageObject(msg_str, src, dst, ack, carrier_len = self.carrier_length)
            self.viewController.send_txt_message(msg)
            self.addMessageToUI(msg, my_message=True)

        if (self.clearOnSend == True):
            text_input_widget.text = ''
            text_input_widget.cursor = (0,0)
            
    def sendGPSBeacon(self):
        self.viewController.gps_one_shot_command()
    
    def selector_pressed(self, selector, pressed_button):
        if (pressed_button.state == 'normal'):
            pressed_button.state = 'down'
            return
        #else:
        for child in selector.children:
            if (child.name != pressed_button.name):
                child.state = 'normal'
        
        if (selector.name == 'modulation_type'):
            self.ini_config['MAIN']['Npoints'] = pressed_button.name
            lbl = self.__get_child_from_base(self.settings_window(), ('settings_root',), 'modulation_type_lbl')
            lbl.text = 'Modulation Scheme (restart required to apply change)'
        elif (selector.name == 'carrier_frequency'):
            self.ini_config['MAIN']['carrier_frequency'] = pressed_button.name
            lbl = self.__get_child_from_base(self.settings_window(), ('settings_root',), 'carrier_frequency_lbl')
            lbl.text = 'Carrier Frequency (restart required to apply change)'
        else:
            return

        updateConfigFile(self.ini_config)
    
    def toggle_pressed(self, toggle_button):
        #print(toggle_button.name)
        #print(toggle_button.state)
        if (toggle_button.name == 'ackChecked'):
            self.ackChecked = True if (toggle_button.state == 'down') else False
        elif (toggle_button.name == 'clearOnSend'):
            self.clearOnSend = True if (toggle_button.state == 'down') else False
        elif (toggle_button.name == 'autoScroll'):
            self.autoScroll = True if (toggle_button.state == 'down') else False
        elif (toggle_button.name == 'enableGPS'):
            self.gps_beacon_enable = True if (toggle_button.state == 'down') else False
            self.viewController.send_gps_beacon_command(self.gps_beacon_enable,self.gps_beacon_period)

    def spinner_pressed(self, spinner):
        if (spinner.name == 'gps_beacon_period'):
            #update the property containing current beacon period
            property = self.__get_child_from_base(self.gps_window(), ('root_gps',), 'current_gps_beacon_period')
            property.value_text = spinner.text
            self.gps_beacon_period = int(spinner.text)
            self.viewController.send_gps_beacon_command(self.gps_beacon_enable,self.gps_beacon_period)

    
    ############## input functions implementing UI_Interface #################
    
    #self.status_updates = deque(maxlen=50) #a queue used to store status updates
    #self.last_status_update_time = time.time #the time of the last status update
    #self.status_update_dwell_time = 0.25 #the dwell time of status updates in seconds
    
    ##@brief the method called by the viewController that will schedule a status update, after the
    ##       dwell time for the previous status update has ellapsed
    ##@param status an integer value that maps to the new status to be added to the queue
    def updateStatusIndicator(self,status):
        if (self.has_ellapsed(self.last_status_update_time,self.status_update_dwell_time)):
            self.status_updates.put(status)
            threading.Timer(0, self.status_update_callback).start()
        else:
            if self.status_updates.full(): #drop the update if the queue is full, this should never happen
                return
            elif self.status_updates.empty(): #add the update to the queue and start the timer   
                self.status_updates.put(status)
                threading.Timer(self.status_update_dwell_time, self.status_update_callback).start()
            else: #the timer is already started, just add the update to the queue
                self.status_updates.put(status)
            
    def status_update_callback(self):
        status = self.status_updates.get()
        self.__updateStatusIndicatorUI(status)
        if not self.status_updates.empty(): #if the queue isn't empty, restart the timer
            threading.Timer(self.status_update_dwell_time, self.status_update_callback).start()

    ##@brief private method that is responsible for updating the status UI's status indicator
    ##@param status, an integer value that maps to the new status
    def __updateStatusIndicatorUI(self,status):
        with self.statusIndicatorLock:
            self.last_status_update_time = time.time()
            root = self.main_window()
            status_indicator = self.__get_child_from_base(root, ('root_main', 'first_row'), 'status_indicator')
            #self.statusIndicatorLock.acquire()
            if (status is Status.SQUELCH_CONTESTED):
                root.indicator_color = root.indicator_pre_rx_color
            if (status is Status.SQUELCH_OPEN):
                root.indicator_color = root.indicator_rx_color 
            elif (status is Status.CARRIER_DETECTED):
                root.indicator_color = root.indicator_rx_color
            elif (status is Status.SQUELCH_CLOSED):
                root.indicator_color = root.indicator_inactive_color
            elif (status is Status.MESSAGE_RECEIVED):
                root.indicator_color = root.indicator_success_color
            elif (status is Status.TRANSMITTING):
                root.indicator_color = root.indicator_tx_color
            else:
                root.indicator_color = root.indicator_inactive_color         
        #self.statusIndicatorLock.release()   
        
    ##@brief add a new message label to the main scroll panel on the gui
    ##@param text_msg A TextMessageObject containing the received message
    ##@param my_message, set to True when this method is being called by this program
    def addMessageToUI(self, text_msg, my_message=False):
        chat_window = self.chat_window()
        message_container = self.__get_child_from_base(chat_window,('root_chat','second_row','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(chat_window, ('root_chat','second_row'), 'scroll_bar')
        
        txt_msg_widget = TextMessage() #create the new widget
        
        #get the strings the widget will be filled with
        header_text = ('{0:s} to {1:s}').format(text_msg.src_callsign, text_msg.dst_callsign)
        time_text = ('{0:s}').format(datetime.now().strftime("%H:%M:%S"))
        message_text = text_msg.msg_str.rstrip('\n')
        
        txt_msg_widget.background_color = chat_window.text_msg_color

        if (text_msg.dst_callsign == self.my_callsign): #if the message was addressed to me
            txt_msg_widget.background_color = chat_window.text_msg_at_color
            message_text = '@' + self.my_callsign + ' ' + message_text
            
        if ((my_message == True) and(text_msg.src_callsign == self.my_callsign)): #if the message was sent by me
            if (text_msg.expectAck == True):
                txt_msg_widget.background_color = chat_window.text_msg_color_ack_pending
            else:
                txt_msg_widget.background_color = chat_window.text_msg_color_no_ack_expect
            sent_time_str = ('sent at {0:s}').format(datetime.now().strftime("%H:%M:%S"))
            ack_time_str = ' | Ack Pending' if (text_msg.expectAck == True) else ''
            time_text = sent_time_str + ack_time_str
        
        txt_msg_widget.header_text = header_text
        txt_msg_widget.time_text = time_text
        txt_msg_widget.message_text = message_text
        message_container.add_widget(txt_msg_widget)
        
        self.messagesLock.acquire()
        self.messages.append(UI_Message(text_msg, txt_msg_widget))
        self.messagesLock.release()
        
        #plyer.notification.notify(title="NoBoB Message Received", message=text_msg.src_callsign, app_name="NoBoB",timeout=10) #send a notification to Android OS
        
        if (self.autoScroll == True):
            scroll_bar.scroll_to(txt_msg_widget)
        
    ##@brief look through the current messages displayed on the ui and delete any that have an ack_key matching the ack_key passed in
    ##@ack_key, a tuple of src, dst, and sequence number forming an ack of messages to delete
    def addAckToUI(self, ack_key):
        self.messagesLock.acquire()
        for msg in self.messages:
            if (msg.ack_key == ack_key):
                ack_time_str = ('Acknowledged at {0:s}').format(datetime.now().strftime("%H:%M:%S"))
                msg.widget.time_text = ack_time_str
                msg.widget.background_color = self.chat_window().text_msg_color_ack_received
        self.messagesLock.release()
        
    @exception_suppressor
    def update_tx_success_cnt(self,val):
        self.__update_property('tx_success_cnt',str(val))
        
    @exception_suppressor
    def update_tx_failure_cnt(self,val):
        self.__update_property('tx_failure_cnt',str(val))
        
    @exception_suppressor
    def update_rx_success_cnt(self,val):
        self.__update_property('rx_success_cnt',str(val))
        
    @exception_suppressor
    def update_rx_failure_cnt(self,val):
        self.__update_property('rx_failure_cnt',str(val))
        
    def __update_property(self,property_name,new_val):
        property = self.__get_child_from_base(self.statistics_window(), ('root_stats',), property_name)
        property.value_text = new_val
    
    def clearReceivedMessages(self):
        return False ###### Note: this isn't really implemented but isn't needed at the moment
    
    def isAckChecked(self):
        return self.ackChecked
        
    def isGPSTxOneShotChecked(self):
        return False
        
    def isGPSTxChecked(self):
        return self.gps_beacon_enable
    
    def getGPSBeaconPeriod(self):
        return self.gps_beacon_period
    
    #@exception_suppressor
    def update_my_displayed_location(self, gps_dict):
        self.__update_gps_property('latitude' ,str(gps_dict['lat']))
        self.__update_gps_property('longitude',str(gps_dict['lon']))
        self.__update_gps_property('speed'    ,str(round(gps_dict['speed'],2)))
        self.__update_gps_property('bearing'  ,str(round(gps_dict['bearing'],2)))
        self.__update_gps_property('altitude' ,str(round(gps_dict['altitude'],2)))
        self.__update_gps_property('accuracy' ,str(round(gps_dict['accuracy'],2)))
            
    def __update_gps_property(self,property_name,new_val):
        property = self.__get_child_from_base(self.gps_window(), ('root_gps',), property_name)
        property.value_text = new_val
        
    def addGPSMessageToUI(self, gps_msg):
        gps_window = self.gps_window()
        message_container = self.__get_child_from_base(gps_window,('root_gps','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(gps_window, ('root_gps',), 'scroll_bar')
        
        gps_msg_widget = TextMessage() #create the new widget
        
        #get the strings the widget will be filled with
        header_text = ('{0:s}').format(gps_msg.src_callsign)
        time_text = ('{0:s}').format(datetime.now().strftime("%H:%M:%S"))
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
    
    def addNewGPSContactToUI(self, gps_msg):
        main_window = self.main_window()
        
        message_container = self.__get_child_from_base(main_window,('root_main','second_row','scroll_bar'), 'message_container')
        scroll_bar = self.__get_child_from_base(main_window, ('root_main','second_row'), 'scroll_bar')
        
        contact_widget = ContactLabel() #create the new widget
        
        contact_widget.callsign_text = gps_msg.src_callsign
        contact_widget.time_text     = ('{0:s}').format(datetime.now().strftime("%H:%M:%S"))
        
        contact_widget.background_color = OSM_COLORS[ (len(self.contact_widgets) % len(OSM_COLORS)) ]
        
        message_container.add_widget(contact_widget) #add the widget to the UI
        self.contact_widgets[gps_msg.src_callsign] = contact_widget #add the widget to a dictionary, where the key is the callsign of the gps message
    
    def updateGPSContact(self, gps_msg):
        if gps_msg.src_callsign in self.contact_widgets:
            widget = self.contact_widgets[gps_msg.src_callsign]
            widget.time_text = ('{0:s}').format(datetime.now().strftime("%H:%M:%S"))
            
    def notifyGPSLockAchieved(self):
        gps_lock_label = self.__get_child_from_base(self.gps_window(),('root_gps',), 'gps_lock_label')
        gps_lock_label.text = "GPS Lock Achieved"
        
    ##@brief update the audio signal strength indicator on the main page of the app
    ##@param signal_strength, floating point value indicating the signal strength, should be between 0.05 and 0.6
    def update_signal_strength(self,signal_strength):
        if (signal_strength < 0.1):
            self.main_window().signal_strength_color = self.main_window().signal_low_color
        elif (signal_strength > 0.5):
            self.main_window().signal_strength_color = self.main_window().signal_high_color
        else:
            self.main_window().signal_strength_color = self.main_window().signal_correct_color
        
        #status_indicator = self.__get_child_from_base(self.main_window(), ('root_main', 'first_row'), 'signal_strength_indicator')
        #status_indicator.text = 
        s = "%2.2f" % (signal_strength)
        self.main_window().signal_strength = s
        
    ################### private functions ##############################
    
    def __apply_ini_config(self, ini_config):
        settings = self.__get_child(self.settings_window(), 'settings_root')

        ack_widget = self.__get_child(settings, 'ackChecked')
        self.ackChecked = True if (ini_config['MAIN']['ack'] == '1') else False
        ack_widget.state = 'down' if self.ackChecked else 'normal'
        
        clear_widget = self.__get_child(settings, 'clearOnSend')
        self.clearOnSend = True if (ini_config['MAIN']['clear'] == '1') else False
        clear_widget.state = 'down' if self.clearOnSend else 'normal'
                
        scroll_widget = self.__get_child(settings, 'autoScroll')
        self.autoScroll = True if (ini_config['MAIN']['scroll'] == '1') else False
        scroll_widget.state = 'down' if self.autoScroll else 'normal'

        dst_callsign_widget = self.__get_child(settings, 'dst_callsign')
        dst_callsign_widget.text = ini_config['MAIN']['dst_callsign']
        self.dstCallsign = ini_config['MAIN']['dst_callsign']
        
        my_callsign_widget = self.__get_child(settings,'my_callsign')
        my_callsign_widget.text = ini_config['MAIN']['my_callsign']
        self.my_callsign = ini_config['MAIN']['my_callsign']  
        
        carrier_length_widget = self.__get_child(settings,'carrier_length')
        carrier_length_widget.text = ini_config['MAIN']['carrier_length']
        self.carrier_length = ini_config['MAIN']['carrier_length']
        
        modulation_selector = self.__get_child(settings, 'modulation_type')
        self.modulation_type = int(ini_config['MAIN']['npoints'])
        self.__get_child(modulation_selector, ini_config['MAIN']['npoints']).state = 'down'
        
        carrier_selector = self.__get_child(settings, 'carrier_frequency')
        self.carrier_frequency = int(ini_config['MAIN']['carrier_frequency'])
        self.__get_child(carrier_selector, ini_config['MAIN']['carrier_frequency']).state = 'down'
        
        gps = self.__get_child(self.gps_window(), 'root_gps')
        
        gps_enable = self.__get_child(gps, 'enableGPS')
        self.gps_beacon_enable = True if (ini_config['MAIN']['gps_beacon_enable'] == '1') else False
        gps_enable.state = 'down' if self.gps_beacon_enable else 'normal'
        
        gps_period = self.__get_child(gps,'gps_beacon_period')
        period_str = ini_config['MAIN']['gps_beacon_period']
        self.gps_beacon_period = int(period_str) if period_str.isdigit() else 30
        gps_period.text = str(self.gps_beacon_period)

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
    
    def _on_keyboard_down(self, instance, keyboard, keycode, text, modifiers):
        if len(modifiers) > 0 and modifiers[0] == 'ctrl' and keycode==40:  # Ctrl+enter
            #print("\nThe key", keycode, "have been pressed")
            #print(" - text is %r" % text)
            #print(" - modifiers are %r" % modifiers)
            
            text_input = self.__get_child_from_base(self.main_window(), ('root_main','third_row'), 'text_input')
            self.sendMessage(text_input)
            
    def _on_keyboard_up(self, instance, keyboard, keycode, text=None, modifiers=None):
        #print(keycode)
        if (keycode == 224): #right control key
            text_input = self.__get_child_from_base(self.main_window(), ('root_main','third_row'), 'text_input')
            text_input.cursor = (0,0)
            
        #if len(modifiers) > 0 and modifiers[0] == 'ctrl' and text=='a':  # Ctrl+a
        #    #self.updateStatusIndicator(5)
        #    text_msg = TextMessageObject(msg_str='message1', src_callsign='BAYWAX', dst_callsign='AAYWAX', expectAck=True, seq_num=None)
        #    self.addMessageToUI(text_msg)
        #    #self.menu.add_menu()          

    ################# override functions #########################
    
    #callback is called when application is started
    def on_start(self, **kwargs):
        self.__apply_ini_config(self.ini_config)