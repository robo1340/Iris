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
from kivy.core.window import Window
kivy.require('1.11.1')

from datetime import datetime
import threading
#import random
import functools
import textwrap
import sys

#Config.set('graphics', 'resizable', False)
#Config.set('graphics', 'width', '1024')
#Config.set('graphics', 'height', '650')

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject
from common import Status

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
    # txt_inpt = ObjectProperty(None)

    # def check_status(self, btn):
        # print('button state is: {state}'.format(state=btn.state))
        # print('text input text is: {txt}'.format(txt=self.txt_inpt))


##@brief instantiate the UI
##@param il2p an IL2P_API object
##@param dst_callsign_initial a string holding the initial value of the dst_callsign_entry
##@param ackCheckedInitial an integer that should be 1 or 0 indicating the initial state of the ackCheckButton
class UiApp(App):
    def __init__(self, il2p, ini_config):
        Window.bind(on_key_down=self._on_keyboard_down)
        Window.bind(on_key_up=self._on_keyboard_up)
        
        self.il2p = il2p
        self.msg_send_queue = il2p.msg_send_queue
        self.ini_config = ini_config
    
        self.testTxEvent = threading.Event()
        self.statusIndicatorLock = threading.Lock()
        
        self.my_callsign = ''
        self.dstCallsign = ''
        self.ackChecked = False
        self.clearOnSend = False
        self.autoScroll = False
        
        self.messagesLock = threading.Lock()
        self.messages = []
    
        super().__init__()
        
    ############### Callback functions called from ui.kv ###############

    def uiSetMyCallsign(self, text_input_widget):
        self.my_callsign = text_input_widget.text.upper().ljust(6,' ')[0:6] #the callsign after being massaged
        text_input_widget.text = self.my_callsign
        self.il2p.setMyCallsign(self.my_callsign)
        
    def uiSetDstCallsign(self, text_input_widget):
        self.dstCallsign = text_input_widget.text.upper().ljust(6,' ')[0:6] #the callsign after being massaged
        text_input_widget.text = self.dstCallsign

    def sendMessage(self, text_input_widget): 
        chunks = lambda str, n : [str[i:i+n] for i in range(0, len(str), n)]  
 
        messages = chunks(text_input_widget.text, 1023) #split the string the user entered into strings of max length 1023
        src = self.my_callsign
        dst = self.dstCallsign
        ack = self.ackChecked
        
        for msg_str in messages:
            msg = TextMessageObject(msg_str, src, dst, ack)
            self.msg_send_queue.put(msg)
            self.addMessageToUI(msg)

        if (self.clearOnSend == True):
            text_input_widget.text = ''
            text_input_widget.cursor = (0,0)

    
    def toggle_pressed(self, toggle_button):
        #print(toggle_button.name)
        #print(toggle_button.state)
        if (toggle_button.name is 'ackChecked'):
            self.ackChecked = True if (toggle_button.state is 'down') else False
        elif (toggle_button.name is 'clearOnSend'):
            self.clearOnSend = True if (toggle_button.state is 'down') else False
        elif (toggle_button.name is 'autoScroll'):
            self.autoScroll = True if (toggle_button.state is 'down') else False
        elif (toggle_button.name is 'testTxVar'):
            if (toggle_button.state is 'down'):
                self.testTxEvent.set()
            else:
                self.testTxEvent.clear()
        
    ############## input functions used to change the UI #################
    
    def updateStatusIndicator(self, status):
        first = self.__get_child(self.root, 'first_row')
        status_indicator = self.__get_child(first, 'status_indicator')
        
        self.statusIndicatorLock.acquire()
        
        if (status is Status.SQUELCH_OPEN):
            self.root.indicator_color = self.root.indicator_rx_color 
        elif (status is Status.CARRIER_DETECTED):
            self.root.indicator_color = self.root.indicator_rx_color
        elif (status is Status.SQUELCH_CLOSED):
            self.root.indicator_color = self.root.indicator_inactive_color
        elif (status is Status.MESSAGE_RECEIVED):
            self.root.indicator_color = self.root.indicator_success_color
        elif (status is Status.TRANSMITTING):
            self.root.indicator_color = self.root.indicator_tx_color
        else:
            self.root.indicator_color = self.root.indicator_inactive_color
            
        self.statusIndicatorLock.release()
        
    ##@brief add a new message label to the main scroll panel on the gui
    ##@param text_msg A TextMessageObject containing the received message
    def addMessageToUI(self, text_msg):
        second_row          = self.__get_child(self.root,'second_row')
        scroll_bar          = self.__get_child(second_row,'scroll_bar')
        message_container   = self.__get_child(scroll_bar,'message_container')
        
        txt_msg_widget = TextMessage() #create the new widget
        
        #get the strings the widget will be filled with
        header_text = ('{0:s} to {1:s} ').format(text_msg.src_callsign, text_msg.dst_callsign)
        time_text = ('received at {0:s}').format(datetime.now().strftime("%H:%M:%S"))
        message_text = text_msg.msg_str.rstrip('\n')
        
        txt_msg_widget.background_color = self.root.text_msg_color

        if (text_msg.dst_callsign == self.my_callsign): #if the message was addressed to me
            txt_msg_widget.background_color = self.root.text_msg_at_color
            message_text = '@' + self.my_callsign + ' ' + message_text
            
        if (text_msg.src_callsign == self.my_callsign): #if the message was sent by me
            if (text_msg.expectAck == True):
                txt_msg_widget.background_color = self.root.text_msg_color_ack_pending
            else:
                txt_msg_widget.background_color = self.root.text_msg_color_no_ack_expect
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
                msg.widget.background_color = self.root.text_msg_color_ack_received
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
        second_row      = self.__get_child(self.root,'second_row')
        right_tool_pane = self.__get_child(second_row,'right_tool_pane')
        property        = self.__get_child(right_tool_pane,property_name)
        property.value_text = new_val
        
    ################### private functions ##############################
    
    def __apply_ini_config(self, ini_config):
        third_row   = self.__get_child(self.root,'third_row')
        lrtp        = self.__get_child(third_row,'lower_right_tool_pane') #get a reference to the lower right tool pane widget
        
        ack_widget = self.__get_child(lrtp, 'ackChecked')
        self.ackChecked = True if (ini_config['MAIN']['ack'] == 'True') else False
        ack_widget.state = 'down' if self.ackChecked else 'normal'
        
        clear_widget = self.__get_child(lrtp, 'clearOnSend')
        self.clearOnSend = True if (ini_config['MAIN']['clear'] == 'True') else False
        clear_widget.state = 'down' if self.clearOnSend else 'normal'
                
        scroll_widget = self.__get_child(lrtp, 'autoScroll')
        self.autoScroll = True if (ini_config['MAIN']['scroll'] == 'True') else False
        scroll_widget.state = 'down' if self.autoScroll else 'normal'

        dst_callsign_widget = self.__get_child(lrtp, 'dst_callsign')
        dst_callsign_widget.text = ini_config['MAIN']['dst_callsign']
        self.dstCallsign = ini_config['MAIN']['dst_callsign']

        first_row = self.__get_child(self.root,'first_row')
        left_top_toolbar = self.__get_child(first_row,'left_top_toolbar')
        
        my_callsign_widget = self.__get_child(left_top_toolbar,'my_callsign')
        my_callsign_widget.text = ini_config['MAIN']['my_callsign']
        self.my_callsign = ini_config['MAIN']['my_callsign']  
    
    def __get_child(self, widget, name):
        for child in widget.children:
            if (child.name is name):
                return child
    
    def _on_keyboard_down(self, instance, keyboard, keycode, text, modifiers):
        if len(modifiers) > 0 and modifiers[0] == 'ctrl' and keycode==40:  # Ctrl+enter
            #print("\nThe key", keycode, "have been pressed")
            #print(" - text is %r" % text)
            #print(" - modifiers are %r" % modifiers)
            
            third = self.__get_child(self.root,'third_row')
            text_input = self.__get_child(third,'text_input')
            self.sendMessage(text_input)
            
    def _on_keyboard_up(self, instance, keyboard, keycode, text=None, modifiers=None):
        #print(keycode)
        if (keycode == 224): #right control key
            third = self.__get_child(self.root,'third_row')
            text_input = self.__get_child(third,'text_input')
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
