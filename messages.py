import numpy as np
import time
import json
import pickle
from datetime import datetime

from kivy.logger import Logger as log

class AckSequenceList():
    @staticmethod
    def unmarshal(str):
        return pickle.loads(str)
    
    def __init__(self):
        self.acks = []
        #self.acks = [0,0,0,0]
        
    def append(self, new_seq, force=False):
        for seq in self.acks:
            if (seq == new_seq) and (forced == False):
                return False
        if (len(self.acks) >= 4):
            self.acks.pop()
        self.acks.insert(0,new_seq)
        return True
        
    
    def getAcksBool(self):
        return len(self.acks)*[True] + (4-len(self.acks))*[False]
        
    def getAcksData(self, my_ack=None):
        toReturn = np.zeros(4, dtype=np.uint16)
        if (my_ack is None):
            for ind, val in enumerate(self.acks):
                toReturn[ind] = val
            log.info(toReturn)
        else:
            toReturn[0] = my_ack
            for ind, val in enumerate(self.acks):
                if (ind == len(self.acks)-1):
                    break
                else:
                    toReturn[ind+1] = val
        return toReturn
    
    def marshal(self):
        return pickle.dumps(self)

class MessageObject():
    
    @staticmethod
    def unmarshal(tup):
        return pickle.loads(tup)
    
    def __init__(self, header=None, payload_str='', attempt_index=0, carrier_len=750, time_str=''):
        self.header = header
        self.payload_str = payload_str
        self.attempt_index = int(attempt_index)
        self.carrier_len = int(carrier_len)
        self.time_str = time_str
        
        self.src_callsign = self.header.src_callsign
        
    def get_ack_seq(self):
        if (self.header.request_double_ack or self.header.request_ack):
            return self.header.data[0]
        else:
            return None
    
    #set the time string
    def mark_time(self):
        self.time_str = datetime.now().strftime("%H:%M:%S")
    
    #extract location from the payload if this message is a gps beacon
    def get_location(self):
        if (self.header.is_beacon == False):
            return None
        else:
            try:
                #convert payload bytes to a dictionary while ignoring all non-ascii characters
                gps_dict = json.loads(self.payload_str.tobytes().decode('ascii','ignore')) 
                log.debug(gps_dict['lat'])
                log.debug(gps_dict['lon'])
                log.debug(gps_dict['altitude'])
                return GPSMessageObject(src_callsign=self.header.src_callsign, location=gps_dict)  
            except BaseException:
                log.warning('WARNING: failed to extract a gps location')
                return None 
    
    def get_dummy_beacon(self):
        return GPSMessageObject(src_callsign=self.header.src_callsign, time_str=self.time_str)
    
    def marshal(self):
        return pickle.dumps(self) 

class GPSMessageObject():
    @staticmethod
    def unmarshal(tup):
        return pickle.loads(tup)
    
    def __init__(self, src_callsign='',location=None, time_str=''):
        self.src_callsign = src_callsign
        self.location = location
        self.time_str = time_str
    
    #extract location from the payload if this message is a gps beacon
    def get_location(self):
        return self.location
    
    def getInfoString(self):
        fmt = 'lat: %8.4f deg, lon: %8.4f deg\nalt: %4.0f m\n' % (self.lat(),self.lon(),self.altitude())
        return fmt
    
    def lat(self):
        try:
            return float(self.location['lat'])
        except BaseException:
            return 0.0
            
    def lon(self):
        try:
            return float(self.location['lon'])
        except BaseException:
            return 0.0

    def altitude(self):
        try:
            return float(self.location['altitude'])
        except BaseException:
            return 0.0

    #set the time string
    def mark_time(self):
        self.time_str = datetime.now().strftime("%H:%M:%S")
    
    def marshal(self):
        return pickle.dumps(self)
    
    