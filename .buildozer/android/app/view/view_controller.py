import threading
import time
import random
import logging
import queue
import random
import time
import sys
from datetime import datetime

#import view.ui

sys.path.insert(0,'..') #need to insert parent path to import something from messages
from messages import TextMessageObject, GPSMessageObject

callsigns = ['BAYWAX','WAYWAX','GBQ98V','YUT5ER','UV8RWE']

samples = [ "hello", 
                "tere", 
                "terevist",
                'yabba',
                'dabba',
                'ding',
                'dong',
                'yippa',
                'And he cried in a loud voice \'Lazarus, come forth\'! And Lazarus did arise from the grave. I have always believed that faith was measured in deeds, not words. And while many of my children worshipped my name, their deeds betrayed them. In my absence they strayed from the path but you, you my son your faith never waned. Not in Honduras or Jericho, not in the Great Rio Insurrection. You risked your life countless times to topple GDI, to perpetuate our cause, to honor my name.',
                'But now I call upon you again to bring glory to the Brotherhood. I have seen that GDI is vulnerable, bloated by arrogance and complacency. Now is the time to strike, while they congratulate themselves on Tiberium advancements Nod made decades ago, we will expose their weaknesses for all the world to see.',
                'AND THEN FART REAL LOUD :3',
                'Twisted Insurrection is a critically acclaimed, standalone modification based on the Command & Conquer Tiberian Sun engine. It features a complete redesign of the original game, set in an alternate what-if? timeline where the Brotherhood of Nod was victorious during the first Tiberian War. Do you have what it takes to drag the shattered Global Defense Initiative out of ruin? Or will you crush all who oppose the will of Kane and his Inner Circle? The choice is yours commander.',
                '...im sorry',
                'lol'
                #'This is me. Literally me. No other character can come close to relating to me like this. There is no way you can convince me this is not me. This character could not possibly be anymore me. It\'s me, and nobody can convince me otherwise. If anyone approached me on the topic of this not possibly being me, then I immediately shut them down with overwhelming evidence that this character is me. This character is me, it is indisputable. Why anyone would try to argue that this character is not me is beyond me. If you held two pictures of me and this character side by side, you\'d see no difference. I can safely look at this character every day and say \"Yup, that\'s me\". I can practically see this character every time I look at myself in the mirror. I go outside and people stop me to comment how similar I look and act to this character. I chuckle softly as I\'m assured everyday this character is me in every way.',
    ]

log = logging.getLogger('__name__')

sampleText = ["hello", "tere", "prevyet"]

##@brief take a text message between 0 and 1023 characters long and send it to the transmit queue
##@brief il2p an IL2P_API object
##@brief msg a TextMessageObject
#def sendTextMessage(send_queue, msg):
#    if (send_queue.full() == True):
#        log.error('ERROR: frame send queue is full')
#    else:
#        send_queue.put(msg) #put the message on a queue to be sent to the radio

def view_controller_func(ui, il2p, ini_config, gps=None, osmand=None):
    tx_time = time.time()
    gps_tx_time = time.time()
    min = int(ini_config['MAIN']['min_wait'])
    max = int(ini_config['MAIN']['max_wait'])
    
    wait_time = random.randint(min,max)

    while (threading.currentThread().stopped() == False):
        if (il2p.msg_output_queue.empty() == False): #there is a received message to be displayed on the ui
            new_msg = il2p.msg_output_queue.get()
            if (isinstance(new_msg, TextMessageObject)):
                ui.addMessageToUI(new_msg)
            elif (isinstance(new_msg, GPSMessageObject)):
                ui.addGPSMessageToUI(new_msg)
                if (osmand is not None):
                    osmand.placeContact(new_msg.lat(), new_msg.lon(), new_msg.src_callsign, datetime.now().strftime("%H:%M:%S")+'\n'+new_msg.getInfoString())
                
        elif (il2p.ack_output_queue.empty() == False): #there is a received ack to be displayed on the ui
            ack_key = il2p.ack_output_queue.get()
            ui.addAckToUI(ack_key)
        
        # if ((ui.isTestTxChecked()) and ((time.time() - tx_time) > wait_time)):
            # tx_time = time.time()
            # wait_time = random.randint(min,max)
            # msg = random.choice(samples)
            # src = il2p.my_callsign
            # dst = 'WAYWAX'
            # #src = random.choice(callsigns).upper().ljust(6,' ')[0:6]
            # #dst = random.choice(callsigns).upper().ljust(6,' ')[0:6]
            # ack = ui.isAckChecked()
        
            # text_msg = TextMessageObject(msg,src,dst,ack)
            # il2p.msg_send_queue.put(text_msg)
            # ui.addMessageToUI(text_msg, my_message=True)
        
        gps_period = ui.getGPSBeaconPeriod()
        
        if (gps is not None):
            if (ui.isGPSTxOneShotChecked()):
                loc = gps.getLocation()
                if (loc is None):
                    continue
                ui.update_my_displayed_location(loc)
                gps_msg = GPSMessageObject(loc, il2p.my_callsign)
                il2p.msg_send_queue.put(gps_msg)
                #ui.addGPSMessageToUI(gps_msg)
                    
            elif ((ui.isGPSTxChecked()) and (time.time() - gps_tx_time) > gps_period ):
                loc = gps.getLocation()
                if (loc is None):
                    continue
                gps_tx_time = time.time() + 0.25*random.uniform(-gps_period, gps_period)
                ui.update_my_displayed_location(loc)

                gps_msg = GPSMessageObject(loc, il2p.my_callsign)
                il2p.msg_send_queue.put(gps_msg)
        
        time.sleep(0.1)  
