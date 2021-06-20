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
        self.length = 4
        
        self.my_ack = 0 #
        
        #self.acks = [0,0,0,0]
    
    #set my acknowledgement to someone requesting an ack from me
    def setMyAck(self, ack): 
        self.my_ack = ack
    
    def append(self, new_seq):
        for seq in self.acks:
            if (seq == new_seq):
                return False
        if (len(self.acks) >= self.length):
            self.acks.pop()
        self.acks.insert(0,new_seq)
        return True
    '''
    def append(self, new_seq, force=False):
        for seq in self.acks:
            if (seq == new_seq) and (force == False):
                return False
        if (len(self.acks) >= self.length):
            self.acks.pop()
        self.acks.insert(0,new_seq)
        return True
    '''
        
    def getAcksBool(self):
        to_return = len(self.acks)*[True] + (self.length-len(self.acks))*[False]
        log.info(to_return)
        return to_return
    
    #my_ack here is an ack I am requesting from someone else
    def getAcksData(self):
        to_return = np.zeros(4, dtype=np.uint16)
            
        for ind, val in enumerate(self.acks):
                to_return[ind] = val
        
        log.info(to_return)
        return to_return
    
    def marshal(self):
        return pickle.dumps(self)

class MessageObject():
    
    @staticmethod
    def unmarshal(tup):
        return pickle.loads(tup)
    
    def __init__(self, header=None, payload_str='', forwarded=False, attempt_index=0, carrier_len=750, time_str=''):
        self.header = header
        self.payload_str = payload_str
        self.attempt_index = int(attempt_index)
        self.carrier_len = int(carrier_len)
        self.time_str = time_str
        self.forwarded = forwarded
        self.priority = 0
        
        self.src_callsign = self.header.src_callsign
        
    def get_ack_seq(self):
        if (self.header.request_double_ack or self.header.request_ack):
            return self.header.getMyAckSequence()
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
                gps_dict = json.loads(self.payload_str) 
                #gps_dict = json.loads(self.payload_str.tobytes().decode('ascii','ignore')) 
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
    
    def __lt__(self, other):
        return self.priority < other.priority

    def __le__(self, other):
        return self.priority <= other.priority
        
    def __gt__(self, other):
        return self.priority > other.priority
        
    def __ge__(self, other):
        return self.priority >= other.priority
        
    def __eq__(self, other):
        return self.priority == other.priority
    
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
    
    