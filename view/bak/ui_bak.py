#Importing Necessary Libraries
import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import scrolledtext
import ctypes
import sys
from datetime import datetime
import view.view_controller



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

    #Screen width and height for the Application
    default_width = 1024
    default_height = 768
    
    #lambda functions that allow you to get a certain percentage of the application screen width or length
    getScreenWidth = lambda percent : int(GUI.default_width*(percent*1.0/100))
    getScreenLength = lambda percent : int(GUI.default_height*(percent*1.0/100))
      
    def __init__(self, send_queue):
        self.send_queue = send_queue
        # super().__init__()
        self.received_messages = []
        
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

        #Call Sign Frame
        callSignFrame = Frame(mainFrame, width=w(100), height=h(15))
        callSignFrame.grid(row=0,column=0, columnspan=3, rowspan=1, sticky='NWE')
        
        #Call Sign Label
        callSignLabel = Label(callSignFrame, text='My Callsign: ', font=('times new roman', 15),  fg='#000000')
        callSignLabel.grid(row=0, column=0, padx=5, pady=5, sticky='W')
        
        #Address Variable which stores the Address 
        src_callsign_var = StringVar()
        src_callsign_var.set('BAYWAX')

        #Address Entry Where the User Enters the Address to which the message will be Sent
        src_callsign_entry = Entry(callSignFrame, textvariable=src_callsign_var, font=('times new roman', 10), width=11)
        src_callsign_entry.grid(row=0, column=1, padx=5, pady=5, sticky='W')
        
        #Left Side Frame
        leftSideFrame = Frame(mainFrame, bd=1, relief='solid', width=w(15), height=h(85))
        leftSideFrame.grid(row=1, column=0, columnspan=1, rowspan=2, padx=5, pady=5, sticky='W')
        
        #Middle Main Frame Upper
        middleMainFrame = Frame(mainFrame, bd=1, relief='solid', width=w(60), height=h(60))
        middleMainFrame.grid(row=1, column=1, columnspan=1, rowspan=1, padx=5, pady=5, sticky='NEW')
        self.middleMainFrame = middleMainFrame
        
        #Middle Main Frame Lower
        secondMiddleMainFrame = Frame(mainFrame, bd=1, relief='solid', width=w(60), height=h(15))
        secondMiddleMainFrame.grid(row=2, column=1, rowspan=1, columnspan=1, sticky='S', padx=5, pady=5)

        #First Right Side Frame
        firstRightSideFrame = Frame(mainFrame, bd=1, relief='solid', width=w(15), height=h(60))
        firstRightSideFrame.grid(row=1, column=2, columnspan=1, rowspan=1, sticky='NW',padx=5,pady=5)

        #Second Right Side Frame
        secondRightSideFrame = Frame(mainFrame, bd=0, relief='solid', width=w(15), height=h(15))
        secondRightSideFrame.grid(row=2, column=2, columnspan=1, rowspan=1, sticky='SW')

        #Ack Label & Checkbox
        ackChecked = IntVar()
        ackCheckButton = Checkbutton(secondRightSideFrame, text="Ack?", font=('times new roman', 10), variable=ackChecked, fg='#000000', padx=10).grid(row=0, column=0, sticky=W)
        
        clearOnSend = IntVar()
        clearOnSendButton = Checkbutton(secondRightSideFrame, text="Clear?", font=('times new roman',10), variable=clearOnSend, fg='#000000', padx=10).grid(row=1,column=0,sticky=W)
        clearOnSend.set(1) #set the button to be checked by default

        #Address Label
        addressLabel = Label(secondRightSideFrame, text='Address to: ', font=('times new roman', 10),  fg='#000000', justify=RIGHT)
        addressLabel.grid(row=2,column=0, sticky=W, padx=5)

        #Address Variable which stores the Address 
        dst_callsign_var = StringVar()

        #Address Entry Where the User Enters the Address to which the message will be Sent
        dst_callsign_entry = Entry(secondRightSideFrame, textvariable=dst_callsign_var, font=('times new roman', 10),width=11)
        dst_callsign_entry.grid(row=2,column=1, sticky=W)
        
        #Address Field set to empty String by default
        dst_callsign_var.set('WAYWAX')

        #Send Button
        def send_button_event_handler(event=None):
            #get the text from the entry's and scrollbar. Massage the input a little bit if needed
            msg = scrollText.get('1.0',tk.END)
            src = src_callsign_var.get().upper().ljust(6,' ')[0:6]
            dst = dst_callsign_var.get().upper().ljust(6,' ')[0:6]
            ack = True if ackChecked.get() else False
            
            view.view_controller.sendTextMessage(self.send_queue,msg,src,dst,ack)
            
            if (clearOnSend.get()):
                scrollText.delete('1.0',tk.END) #delete the contents of the scrolled text
            
            #set the text in the entry fields if the input was massaged
            src_callsign_var.set(src)
            dst_callsign_var.set(dst)
            
        sendButton = Button(secondRightSideFrame, text='Send', command=send_button_event_handler, font=('times new roman', 10))
        sendButton.grid(row=4, sticky=W, padx=10, pady=4)
        self.bind("<Return>",send_button_event_handler)

        self.update()
        #Parts Inside Middle Frame
        
        #Scrollable Chat Frame
        chatCanvas = tk.Canvas(middleMainFrame, width=w2(middleMainFrame,100), height=h2(middleMainFrame,100))
        scrollbar = ttk.Scrollbar(middleMainFrame, orient='vertical', command=chatCanvas.yview)
        self.scrollableFrame = ttk.Frame(chatCanvas)

        self.scrollableFrame.bind(
            "<Configure>",
            lambda e: chatCanvas.configure(
                scrollregion=chatCanvas.bbox("all")
            )
        )

        chatCanvas.create_window((0,0), window=self.scrollableFrame, anchor='nw')
        chatCanvas.configure(yscrollcommand=scrollbar.set)
        
        chatCanvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        
        #Scrollable Message Frame Where the User will enter the Message
        scrollText = scrolledtext.ScrolledText(secondMiddleMainFrame, wrap=WORD, height=10)
        scrollText.pack(side=LEFT, fill=BOTH, expand=False)
        scrollText.focus_set()
        
        self.update()

    ##@brief add a new message label to the main scroll panel on the gui
    ##@param text_msg A TextMessageObject containing the received message
    def addReceivedMessage(self, text_msg):
        fmt_str = ('From {0:s}: Received at : {1:s}\n{2:s}')
        str = fmt_str.format(text_msg.dst_callsign, datetime.now().strftime("%H:%M:%S"), text_msg.msg_str)
        
        self.middleMainFrame.update()
        #print(self.middleMainFrame.winfo_width())
        lbl = ttk.Label(self.scrollableFrame, text=str, wraplength=self.middleMainFrame.winfo_width()-15, justify=LEFT)
        lbl.pack()
    
        self.received_messages.append(lbl)
    
    
    def clearReceivedMessages(self):
        for lbl in self.received_messages:
            lbl.destroy()

    def init_ui(self):

        #Setting the App Screen Resolution    
        #screenResolution = ctypes.windll.user32  
        #print(screenResolution.GetSystemMetrics(0))
        #print(screenResolution.GetSystemMetrics(1))
        
        #Adding the Title, App Width & Height, set Resizable to False, and added an Icon
        self.title('User Interface')
        self.geometry(str(GUI.default_width) + 'x' + str(GUI.default_height))
        self.resizable(True, True)
        self.iconbitmap('resources/icons/home.ico')
        self.mainloop()


       

