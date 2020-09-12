#Importing Necessary Libraries
import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import scrolledtext
import ctypes
import sys
from datetime import datetime
import view.view_controller
import threading
import functools
import textwrap
import random

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject
from common import Status

'''
def timing_function(some_function):
    def wrapper(*args,**kwargs):
        t1 = time.time()
        some_function(*args,**kwargs)
        t2 = time.time()
        return "Time it took to run: " + str((t2-t1)) + "\n"
    return wrapper
'''

def exception_suppressor(func):
    def meta_function(*args, **kwargs):
        try:
            func(*args,**kwargs)
        except BaseException:
            pass
    return meta_function
        
class UI_Message():
    def __init__(self, msg, frame):
        self.ack_key = (msg.src_callsign,msg.dst_callsign,msg.seq_num) if (msg.expectAck == True) else ('','',0)
        self.frame = frame

#Creating Class MenuBar place on Top
class MenuBar(tk.Menu):
    def __init__(self, parent):
        tk.Menu.__init__(self, parent)

        #Creating the File Menu
        fileMenu = tk.Menu(self, tearoff=0)
        self.add_cascade(label="File",underline=0, menu=fileMenu)
        fileMenu.add_command(label="Exit", underline=1, command=self.quit)
        #Creating the Options Menu with 3 Options in it which are attached to doSomething Function
        optionsMenu = tk.Menu(self, tearoff=0)
        self.add_cascade(label="Options",underline=0, menu=optionsMenu)
        optionsMenu.add_command(label="Option 1", underline=1, command=self.doSomething)
        optionsMenu.add_command(label="Option 2", underline=1, command=self.doSomething)
        optionsMenu.add_command(label="Option 3", underline=1, command=self.doSomething)
    
    #Quit Function for Exit option in File Menu
    def quit(self):
        sys.exit(0)
    
    #doSomething Function
    def doSomething(self):
        return

#Creating the Main Class Here
class GUI(tk.Tk):
    default_font = ('times new roman', 10)

    at_color = 'IndianRed1'
    default_color = 'gainsboro'
    
    indicator_rx1_color = 'dodger blue'
    indicator_rx2_color = 'blue'
    indicator_rx_success_color = 'green'
    indicator_tx_color = 'red'
    indicator_inactive_color = 'black'

    #Screen width and height for the Application
    default_width = 1024
    default_height = 650#768
    
    #lambda functions that allow you to get a certain percentage of the application screen width or length
    getScreenWidth = lambda percent : int(GUI.default_width*(percent*1.0/100))
    getScreenLength = lambda percent : int(GUI.default_height*(percent*1.0/100))
     
    ##@brief instantiate the UI
    ##@param il2p an IL2P_API object
    ##@param dst_callsign_initial a string holding the initial value of the dst_callsign_entry
    ##@param ackCheckedInitial an integer that should be 1 or 0 indicating the initial state of the ackCheckButton
    def __init__(self, il2p, ini_config):
        self.testTxEvent = threading.Event()
        self.statusIndicatorLock = threading.Lock()
        self.messagesLock = threading.Lock()
    
        self.il2p = il2p
        self.msg_send_queue = il2p.msg_send_queue
        # super().__init__()
        self.messages = []
        
        tk.Tk.__init__(self)
        menubar = MenuBar(self)
        self.config(menu=menubar)

        #Initiating the Main Frame which contains all the Frames and Widgets
        mainFrame = Frame(self, bd=1, relief='solid')
        mainFrame.place(x=0,y=0, width=GUI.getScreenWidth(100), height=GUI.getScreenLength(100))
        self.update()
        
        w = lambda percent : int(mainFrame.winfo_width()*(percent*1.0/100))
        h = lambda percent : int(mainFrame.winfo_height()*(percent*1.0/100))
        
        w2 = lambda frame, percent : int(frame.winfo_width()*(percent*1.0/100))
        h2 = lambda frame, percent : int(frame.winfo_height()*(percent*1.0/100))
        self.w2 = w2

        mainFrame.grid_rowconfigure(1,weight=1)
        #mainFrame.grid_columnconfigure(2,weight=1)

        #Call Sign Frame
        toolFrame = Frame(mainFrame, width=w(100), height=h(15))
        toolFrame.grid(row=0,column=0, columnspan=3, rowspan=1, sticky='NWE',padx=5, pady=5)
        toolFrame.grid_rowconfigure(0,weight=1)
        toolFrame.grid_columnconfigure(2, weight=1)
        
        #Call Sign Label
        callSignLabel = Label(toolFrame, text='My Callsign: ', font=('times new roman', 15),  fg='#000000')
        callSignLabel.grid(row=0, column=0, padx=5, pady=5, sticky='W')
        
        #Address Variable which stores the Address 
        self.src_callsign_var = StringVar()
        
        def src_callsign_changed_event_handler(name, index, mode):
            pre_var = self.src_callsign_var.get() #the callsign before being massaged
            post_var = self.src_callsign_var.get().upper().ljust(6,' ')[0:6] #the callsign after being massaged
            if (pre_var != post_var):
                self.src_callsign_var.set(post_var)
            il2p.setMyCallsign(self.src_callsign_var.get())  
        
        self.src_callsign_var.trace("w", src_callsign_changed_event_handler)
        #self.src_callsign_var.trace("w", lambda name, index, mode, sv=self.src_callsign_var: src_callsign_changed_event_handler(sv))
        #self.src_callsign_var.trace_add('write', src_callsign_changed_event_handler) 
        self.src_callsign_var.set(self.il2p.my_callsign)

        #Address Entry Where the User Enters his callsign
        src_callsign_entry = Entry(toolFrame, textvariable=self.src_callsign_var, font=('times new roman', 10), width=11)
        src_callsign_entry.grid(row=0, column=1, padx=5, pady=5, sticky='W')
        
        #next to the Address Entry place the tx/rx indicator
        toolFrame.update()
        self.rxtx_indicator = Frame(toolFrame, bd=1, relief='solid', width=h2(toolFrame,100), height=h2(toolFrame,100), bg=GUI.indicator_inactive_color)
        self.rxtx_indicator.grid(row=0, column=2, padx=2, pady=2, sticky='E')
        
        #Left Side Frame
        leftSideFrame = Frame(mainFrame, bd=1, relief='solid', width=w(15), height=h(85))
        leftSideFrame.grid(row=1, column=0, columnspan=1, rowspan=2, padx=5, pady=5, sticky='NSW')
        
        #Middle Main Frame Upper
        middleMainFrame = Frame(mainFrame, bd=1, relief='solid', width=w(60), height=h(65))
        middleMainFrame.grid(row=1, column=1, columnspan=1, rowspan=1, padx=5, pady=5, sticky=NSEW)
        self.middleMainFrame = middleMainFrame
        
        #Middle Main Frame Lower
        secondMiddleMainFrame = Frame(mainFrame, bd=1, relief='solid', width=w(60), height=h(10))
        secondMiddleMainFrame.grid(row=2, column=1, rowspan=1, columnspan=1, sticky='SEW', padx=5, pady=5)

        #First Right Side Frame
        firstRightSideFrame = Frame(mainFrame, bd=1, relief='solid', width=w(15), height=h(65))
        firstRightSideFrame.grid(row=1, column=2, columnspan=1, rowspan=1, sticky=NSEW,padx=5,pady=5)
        
        tx_success_lbl1 = Label(firstRightSideFrame, text='tx success:', font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=0, column=0, sticky='W')
        tx_failure_lbl1 = Label(firstRightSideFrame, text='tx failure:', font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=1, column=0, sticky='W')
        rx_success_lbl1 = Label(firstRightSideFrame, text='rx success:', font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=2, column=0, sticky='W')
        rx_failure_lbl1 = Label(firstRightSideFrame, text='rx failure:', font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=3, column=0, sticky='W')
        
        self.tx_success_str = StringVar(value='0')
        self.tx_failure_str = StringVar(value='0')
        self.rx_success_str = StringVar(value='0')
        self.rx_failure_str = StringVar(value='0')
        
        tx_success_lbl2 = Label(firstRightSideFrame, textvariable=self.tx_success_str, font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=0, column=1, sticky='E')
        tx_failure_lbl2 = Label(firstRightSideFrame, textvariable=self.tx_failure_str, font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=1, column=1, sticky='E')
        rx_success_lbl2 = Label(firstRightSideFrame, textvariable=self.rx_success_str, font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=2, column=1, sticky='E')
        rx_failure_lbl2 = Label(firstRightSideFrame, textvariable=self.rx_failure_str, font=GUI.default_font, width=w2(firstRightSideFrame,50)).grid(row=3, column=1, sticky='E')
        
        #test send check box event handler
        def send_test_message_event_handler(event=None):
            if self.testTxVar.get() == True:
                self.testTxEvent.set()
            else:
                self.testTxEvent.clear()
        
        self.testTxVar = IntVar()
        testTxButton = Checkbutton(firstRightSideFrame, text="Test tx?", font=GUI.default_font, width=w2(firstRightSideFrame,50), variable=self.testTxVar, command=send_test_message_event_handler).grid(row=4,column=0,sticky=E, columnspan=1)

        #Second Right Side Frame
        secondRightSideFrame = Frame(mainFrame, bd=0, relief='solid', width=w(15), height=h(10))
        secondRightSideFrame.grid(row=2, column=2, columnspan=1, rowspan=1, sticky='SEW')

        #Ack Label & Checkbox
        self.ackChecked = IntVar()
        ackCheckButton = Checkbutton(secondRightSideFrame, text="Ack?", font=('times new roman', 10), variable=self.ackChecked, fg='#000000', padx=10).grid(row=0, column=0, sticky=W)
        self.ackChecked.set(ini_config['MAIN']['ack'])
        
        clearOnSend = IntVar()
        clearOnSendButton = Checkbutton(secondRightSideFrame, text="Clear?", font=('times new roman',10), variable=clearOnSend, fg='#000000', padx=10).grid(row=1,column=0,sticky=W)
        clearOnSend.set(ini_config['MAIN']['clear']) #set the button to be checked by default

        self.autoScroll = IntVar()
        autoScrollButton = Checkbutton(secondRightSideFrame, text='Scroll?', font=('times new roman',10), variable=self.autoScroll, fg='#000000', padx=10).grid(row=2,column=0,sticky=W)
        self.autoScroll.set(ini_config['MAIN']['scroll'])

        #Address Label
        addressLabel = Label(secondRightSideFrame, text='Address to: ', font=('times new roman', 10),  fg='#000000', justify=RIGHT)
        addressLabel.grid(row=3,column=0, sticky=W)

        #Address Variable which stores the Address 
        self.dst_callsign_var = StringVar()

        #Address Entry Where the User Enters the Address to which the message will be Sent
        dst_callsign_entry = Entry(secondRightSideFrame, textvariable=self.dst_callsign_var, font=('times new roman', 10),width=11)
        dst_callsign_entry.grid(row=3,column=1, sticky=W)
        
        #Address Field set to empty String by default
        self.dst_callsign_var.set(ini_config['MAIN']['dst_callsign'])

        #Send Button
        def send_button_event_handler(event=None):
            chunks = lambda str, n : [str[i:i+n] for i in range(0, len(str), n)]
            
            messages = chunks(scrollText.get('1.0',tk.END), 1023) #split the string the user entered into strings of max length 1023
            src = self.src_callsign_var.get()
            dst = self.dst_callsign_var.get().upper().ljust(6,' ')[0:6]
            ack = True if self.ackChecked.get() else False
            
            for msg_str in messages:
                msg = TextMessageObject(msg_str, src, dst, ack)
                view.view_controller.sendTextMessage(self.msg_send_queue, msg)
                self.addMessageToUI(msg)
            
            if (clearOnSend.get()):
                scrollText.delete('1.0',tk.END) #delete the contents of the scrolled text
                
            #set the text in the entry fields if the input was massaged
            self.dst_callsign_var.set(dst)
            
        sendButton = Button(secondRightSideFrame, text='Send', command=send_button_event_handler, font=('times new roman', 10))
        sendButton.grid(row=4, sticky=W, padx=10, pady=4)
        self.bind("<Control-Return>",send_button_event_handler)

        self.update()
        #Parts Inside Middle Frame
        
        #Scrollable Chat Frame
        self.chatCanvas = tk.Canvas(middleMainFrame, width=w2(middleMainFrame,100), height=h2(middleMainFrame,100))
        self.scrollbar = ttk.Scrollbar(middleMainFrame, orient='vertical', command=self.chatCanvas.yview)
        self.scrollableFrame = ttk.Frame(self.chatCanvas)

        self.scrollableFrame.bind(
            "<Configure>",
            lambda e: self.chatCanvas.configure(
                scrollregion=self.chatCanvas.bbox("all")
            )
        )

        self.chatCanvas.create_window((0,0), window=self.scrollableFrame, anchor='nw')
        self.chatCanvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.chatCanvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)

        
        #Scrollable Message Frame Where the User will enter the Message
        scrollText = scrolledtext.ScrolledText(secondMiddleMainFrame, wrap=WORD, height=10)
        scrollText.pack(side=LEFT, fill=BOTH, expand=False)
        scrollText.focus_set()
        
        self.update()

    ##@brief add a new message label to the main scroll panel on the gui
    ##@param text_msg A TextMessageObject containing the received message
    def addMessageToUI(self, text_msg):
        self.middleMainFrame.update() #update the middle frame so that winfo_width() will be correct
        
        #fmt_str = ('From {0:s}: Received at : {1:s}\n{2:s}')
        #str = fmt_str.format(text_msg.dst_callsign, datetime.now().strftime("%H:%M:%S"), text_msg.msg_str)
        width = self.middleMainFrame.winfo_width()
        
        callsign_str = ('{0:s}: ').format(text_msg.src_callsign)
        time_str = ('received at {0:s}').format(datetime.now().strftime("%H:%M:%S"))
        time_var = StringVar(value=time_str)
        msg_str = text_msg.msg_str.rstrip('\n')
        frame_bg = GUI.default_color

        if (text_msg.dst_callsign == self.src_callsign_var.get()): #if the message was addressed to me
            frame_bg = GUI.at_color
            msg_str = '@' + self.src_callsign_var.get() + ' ' + msg_str
            
        if (text_msg.src_callsign == self.il2p.my_callsign): #if the message was sent by me
            sent_time_str = ('sent at {0:s}').format(datetime.now().strftime("%H:%M:%S"))
            ack_time_str = ' | Ack Pending' if (text_msg.expectAck == True) else ''
            time_var.set(sent_time_str + ack_time_str)
        
        newFrame = Frame(self.scrollableFrame, bd=1, bg=frame_bg, relief='solid', width=width)
        
        callsign_lbl = Label(newFrame, text=callsign_str, justify=LEFT, bg=frame_bg).grid(row=0, column=0, sticky=NW)
        time_lbl = Label(newFrame, text=time_var.get(), justify=LEFT, bg=frame_bg).grid(row=0,column=1, sticky=NW)
        msg_lbl = Label(newFrame, text=msg_str, justify=LEFT, wraplength=width-25, bg=frame_bg).grid(row=1,column=0, rowspan=1, columnspan=2, sticky=NW)
        
        newFrame.pack(anchor=W, side=TOP)
        newFrame.grid_columnconfigure(1, weight=1)
        
        if (self.autoScroll.get() == True):
            self.chatCanvas.yview_moveto( 1 ) #scroll to the bottom since a new message has been received
        
        self.messagesLock.acquire()
        self.messages.append(UI_Message(text_msg, newFrame))
        self.messagesLock.release()
    
    ##@brief look through the current messages displayed on the ui and delete any that have an ack_key matching the ack_key passed in
    ##@ack_key, a tuple of src, dst, and sequence number forming an ack of messages to delete
    def addAckToUI(self, ack_key):
        self.messagesLock.acquire()
        for msg in self.messages:
            if (msg.ack_key == ack_key):
                ack_time_str = ('Acknowledged at {0:s}').format(datetime.now().strftime("%H:%M:%S"))
                msg.frame.winfo_children()[1].config(text=ack_time_str)
        self.messagesLock.release()
    
    def updateStatusIndicator(self, status):
        self.statusIndicatorLock.acquire()
    
        if (status is Status.SQUELCH_OPEN):
            self.rxtx_indicator.configure(bg=GUI.indicator_rx1_color)
        elif (status is Status.CARRIER_DETECTED):
            self.rxtx_indicator.configure(bg=GUI.indicator_rx2_color)
        elif (status is Status.SQUELCH_CLOSED):
            self.rxtx_indicator.configure(bg=GUI.indicator_inactive_color)
        elif (status is Status.MESSAGE_RECEIVED):
            self.rxtx_indicator.configure(bg=GUI.indicator_rx_success_color)
        elif (status is Status.TRANSMITTING):
            self.rxtx_indicator.configure(bg=GUI.indicator_tx_color)
        else:
            self.rxtx_indicator.configure(bg=GUI.indicator_inactive_color)
            
        self.statusIndicatorLock.release()
    
    @exception_suppressor
    def update_tx_success_cnt(self,val):
        self.tx_success_str.set(str(val))
        
    @exception_suppressor
    def update_tx_failure_cnt(self,val):
        self.tx_failure_str.set(str(val))
        
    @exception_suppressor
    def update_rx_success_cnt(self,val):
        self.rx_success_str.set(str(val))
        
    @exception_suppressor
    def update_rx_failure_cnt(self,val):
        self.rx_failure_str.set(str(val))
    
    def clearReceivedMessages(self):
        self.messagesLock.acquire()
        for i in range(0, len(self.messages)):
            msg = self.messages.pop()
            msg.frame.destroy()
        self.messagesLock.release()

    def init_ui(self):

        #Setting the App Screen Resolution    
        #screenResolution = ctypes.windll.user32  
        #print(screenResolution.GetSystemMetrics(0))
        #print(screenResolution.GetSystemMetrics(1))
        
        #Adding the Title, App Width & Height, set Resizable to False, and added an Icon
        self.title('User Interface')
        self.geometry(str(GUI.default_width) + 'x' + str(GUI.default_height) + '+0+0')
        self.resizable(True, True)
        self.iconbitmap('resources/icons/home.ico')
        self.mainloop()


       

