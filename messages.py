import random
import time
import json
import logging

log = logging.getLogger('__name__')

class TextMessageObject():

    @staticmethod
    def unmarshal(tup):
        ack = True if (tup[3] == 'True') else False
        return TextMessageObject(tup[0], tup[1], tup[2], ack, int(tup[4]), int(tup[5]), int(tup[6]) )

    def __init__(self, msg_str='', src_callsign='', dst_callsign='', expectAck=False, seq_num=None, attempt_index=0, carrier_len=750):
        self.msg_str = msg_str
        self.src_callsign = src_callsign
        self.dst_callsign = dst_callsign
        self.expectAck = expectAck
        if ((self.expectAck == True) and (seq_num==None)): #if an ack is expected for this message and the seq_num passed in is the default
            self.seq_num = random.randint(1,127) #choose a number from 1 to 127
        elif ((self.expectAck == False) and (seq_num==None)):
            self.seq_num = 0
        else:
            self.seq_num = seq_num
        self.attempt_index = attempt_index
        self.carrier_len = carrier_len
        
    def getInfoString(self):
        fmt = 'SRC Callsign: [{0:s}], DST Callsign: [{1:s}], Ack?: {3:s}, sequence#: {4:s}, Message: {2:s}'
        return fmt.format(self.src_callsign, self.dst_callsign, self.msg_str.strip('\n'), str(self.expectAck), str(self.seq_num))
       
    def print(self):
        print(self.getInfoString())
        
    def marshal(self):
        return (self.msg_str, self.src_callsign, self.dst_callsign, str(self.expectAck), str(self.seq_num), str(self.attempt_index), str(self.carrier_len))
        
        
class GPSMessageObject():

    @staticmethod
    def unmarshal(tup):
        try:
            gps_dict = json.loads( tup[0] )
            log.debug(gps_dict['lat'])
            log.debug(gps_dict['lon'])
            log.debug(gps_dict['altitude'])
            return GPSMessageObject(gps_dict, tup[1])  
        except BaseException:
            log.warning('WARNING: failed to unmarshal a gps message')
            return None   

    ##@brief constructor for a GPSMessageObject
    ##@param location a dictionary object containing the current location, speed, bearing etc.
    ##@param src_callsign the callsign of the radio sending this gps message
    def __init__(self, location, src_callsign='',carrier_len=750):
        self.location = location
        self.src_callsign = src_callsign
        self.carrier_len = carrier_len
       
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
        
    def print(self):
        print(self.getInfoString())
        
    def marshal(self):
        loc = str(self.location).replace('\'','\"')
        return (loc, self.src_callsign, str(self.carrier_len))
    