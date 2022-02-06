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
    
    def __init__(self, header=None, payload_str='', forwarded=False, attempt_index=0, carrier_len=750, time_str='', priority=100):
        self.header = header
        self.payload_str = payload_str
        self.attempt_index = int(attempt_index)
        self.carrier_len = int(carrier_len)
        self.time_str = time_str
        self.forwarded = forwarded
        self.priority = priority
        
        self.src_callsign = self.header.src_callsign
        
    get_dummy_beacon = lambda self : GPSMessageObject(src_callsign=self.header.src_callsign, time_str=self.time_str)
    marshal = lambda self : pickle.dumps(self)
    __lt__ = lambda self, other : (self.priority < other.priority)
    __le__ = lambda self, other : (self.priority <= other.priority)
    __gt__ = lambda self, other : (self.priority > other.priority)
    __ge__ = lambda self, other : (self.priority >= other.priority)
    __eq__ = lambda self, other : (self.priority == other.priority)
    mark_time = lambda self : datetime.now().strftime("%H:%M:%S")
        
    def get_ack_seq(self):
        if (self.header.request_double_ack or self.header.request_ack):
            return self.header.getMyAckSequence()
        else:
            return None
    
    #extract location from the payload if this message is a gps beacon
    def get_location(self):
        if (self.header.is_beacon == False):
            return None
        else:
            try:
                #convert payload bytes to a dictionary while ignoring all non-ascii characters
                gps_dict = json.loads(self.payload_str) 
                #gps_dict = json.loads(self.payload_str.tobytes().decode('ascii','ignore')) 
                gps_dict['lat'] = float(gps_dict['lat'])
                gps_dict['lon'] = float(gps_dict['lon'])
                gps_dict['altitude'] = float(gps_dict['altitude'])
                return GPSMessageObject(src_callsign=self.header.src_callsign, location=gps_dict)  
            except BaseException:
                log.warning('WARNING: failed to extract a gps location')
                return None 
    
    ##@brief extract a dictionary of waypoints from the payload if this message is a waypoint beacon
    def get_waypoints(self):
        if (self.header.is_waypoint == False):
            return None
        else:
            try:
                waypoints = json.loads(self.payload_str) 
                for key,val in waypoints.items():
                    waypoints[key] = [float(val[0]),float(val[1])]
                #log.info(waypoints)
                return WaypointMessageObject(src_callsign=self.header.src_callsign, waypoints=waypoints)  
            except BaseException:
                log.warning('WARNING: failed to extract a waypoints from payload')
                return None 
    
class GPSMessageObject():

    @staticmethod
    def unmarshal(tup):
        return pickle.loads(tup)
    
    def __init__(self, src_callsign='',location=None, time_str=''):
        self.src_callsign = src_callsign
        self.location = location
        self.time_str = time_str
        
    get_location = lambda self : self.location
    getInfoString = lambda self : 'lat: %8.4f deg, lon: %8.4f deg\nalt: %4.0f m\n' % (self.lat(),self.lon(),self.altitude())
    mark_time = lambda self : datetime.now().strftime("%H:%M:%S")
    marshal = lambda self : pickle.dumps(self)
    lat = lambda self : self.location['lat']
    lon = lambda self : self.location['lon']
    altitude = lambda self : self.location['altitude']
    
class WaypointMessageObject():
    
    @staticmethod
    def unmarshal(tup):
        return pickle.loads(tup)
    
    def __init__(self, src_callsign='',waypoints=None, time_str=''):
        self.src_callsign = src_callsign
        self.time_str = time_str
        self.waypoints = waypoints #a dictionary object containg waypoints
        
    getInfoString = lambda self : str(self.waypoints)
    mark_time = lambda self : datetime.now().strftime("%H:%M:%S")
    marshal = lambda self : pickle.dumps(self)
        