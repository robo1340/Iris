#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
#import argparse


import numpy as np
import time
from queue import PriorityQueue

#sys.path.insert(0,'..') #need to insert parent path to import something from messages

from func_timeout import func_set_timeout, FunctionTimedOut

import common
import config
import IL2P_API
from IL2P import *
from messages import *


from kivy.logger import Logger as log

###################################################################        
######################## IL2P API TEST ############################
################################################################### 
if __name__ == "__main__":

    #args = parseCommandLineArguments()
    ini_config = common.parseConfigFile(common.CONFIG_FILE_NAME)
    if not common.verify_ini_config(ini_config):
        raise Exception('Error: Not all needed values were found in the .ini configuration file')

    il2p = IL2P_API.IL2P_API(ini_config=ini_config, verbose=False)#, msg_send_queue=msg_send_queue)
    
    acks = AckSequenceList()
    acks.append(1337)
    acks.append(1338)
    acks.append(1339)    
    
    #def getAcksBool(self):   
    #def getAcksData(self, my_ack=None):
    
    hdr1 = IL2P_Frame_Header(src_callsign='BAYWAX', dst_callsign='WAYWAX', \
                           hops_remaining=1, hops=2, is_text_msg=False, is_beacon=True, \
                           stat1=False, stat2=False, \
                           acks=acks.getAcksBool(),
                           request_ack=False, request_double_ack=False, \
                           payload_size=0, \
                           data=acks.getAcksData())
    hdr1.print_header()
    
    
    il2p.processFrame(hdr1, '', test=True)
    
    
    
