import threading
import time
import random
import logging
import queue
import random
import time

import view.ui

callsigns = ['BAYWAX','WAYWAX','GBQ98V','YUT5E','UV8RWE']

samples = [ "hello", 
                "tere", 
                "prevyet",
                'yabba',
                'dabba',
                'ding',
                'dong',
                'yippa',
                'dildonic',
                'butfuckery',
                'And he cried in a loud voice \'Lazarus, come forth\'! And Lazarus did arise from the grave. I have always believed that faith was measured in deeds, not words. And while many of my children worshipped my name, their deeds betrayed them. In my absence they strayed from the path but you, you my son your faith never waned. Not in Honduras or Jericho, not in the Great Rio Insurrection. You risked your life countless times to topple GDI, to perpetuate our cause, to honor my name.',
                'But now I call upon you again to bring glory to the Brotherhood. I have seen that GDI is vulnerable, bloated by arrogance and complacency. Now is the time to strike, while they congratulate themselves on Tiberium advancements Nod made decades ago, we will expose their weaknesses for all the world to see.',
                'AND THEN FART REAL LOUD :3',
                'Twisted Insurrection is a critically acclaimed, standalone modification based on the Command & Conquer Tiberian Sun engine. It features a complete redesign of the original game, set in an alternate what-if? timeline where the Brotherhood of Nod was victorious during the first Tiberian War. Do you have what it takes to drag the shattered Global Defense Initiative out of ruin? Or will you crush all who oppose the will of Kane and his Inner Circle? The choice is yours commander.',
                '...im sorry',
                'lol',
                'This is me. Literally me. No other character can come close to relating to me like this. There is no way you can convince me this is not me. This character could not possibly be anymore me. It\'s me, and nobody can convince me otherwise. If anyone approached me on the topic of this not possibly being me, then I immediately shut them down with overwhelming evidence that this character is me. This character is me, it is indisputable. Why anyone would try to argue that this character is not me is beyond me. If you held two pictures of me and this character side by side, you\'d see no difference. I can safely look at this character every day and say \"Yup, that\'s me\". I can practically see this character every time I look at myself in the mirror. I go outside and people stop me to comment how similar I look and act to this character. I chuckle softly as I\'m assured everyday this character is me in every way.',
    ]

log = logging.getLogger('__name__')

sampleText = ["hello", "tere", "prevyet"]

##@brief take a text message between 0 and 1023 characters long and send it to the transmit queue
##@param src_callsign the callsign of the sender
##@param dst_callsign the intended recipient of the message, though anyone can receive it
##@param requestAck, True if the sender is requesting an acknowledgment from the intended recipient 
def sendTextMessage(send_queue,msg,src_callsign,dst_callsign,requestAck):
    
    seq_num = 0
    if (requestAck):
        seq_num = random.randint(0,127)
    
    msg = TextMessageObject(msg, src_callsign, dst_callsign, requestAck, seq_num)
    #msg.print()
    send_queue.put(msg) #put the message on a queue to be sent to the radio

class TextMessageObject():
    def __init__(self, msg_str='', src_callsign='', dst_callsign='', expectAck=False, seq_num=0):
        self.msg_str = msg_str
        self.src_callsign = src_callsign
        self.dst_callsign = dst_callsign
        self.expectAck = expectAck
        self.seq_num = seq_num
        
    def getInfoString(self):
        fmt = 'SRC Callsign: [{0:s}], DST Callsign: [{1:s}], Ack?: {3:s}, sequence#: {4:s}, Message: {2:s}'
        return fmt.format(self.src_callsign, self.dst_callsign, self.msg_str.strip('\n'), str(self.expectAck), str(self.seq_num))
       
    def print(self):
        print(self.getInfoString())
        

def view_controller_func(ui,send_queue,recv_queue):
    tx_time = time.time()
    wait_time = random.randint(10,20)

    while (threading.currentThread().stopped() == False):
        if (recv_queue.empty() == False): #there is a received message to be displayed on the ui
            new_msg = recv_queue.get()            
            ui.addReceivedMessage(new_msg)    
        time.sleep(0.1)
        
        if ((ui.testTxEvent.isSet()) and ((time.time() - tx_time) > wait_time)):
            tx_time = time.time()
            wait_time = random.randint(5,10)
            msg = random.choice(samples)
            src = random.choice(callsigns).upper().ljust(6,' ')[0:6]
            dst = random.choice(callsigns).upper().ljust(6,' ')[0:6]
            ack = True if ui.ackChecked.get() else False
        
            view.view_controller.sendTextMessage(send_queue,msg,src,dst,ack)
            
