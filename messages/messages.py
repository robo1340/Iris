import random


class TextMessageObject():
    def __init__(self, msg_str='', src_callsign='', dst_callsign='', expectAck=False, seq_num=None):
        self.msg_str = msg_str
        self.src_callsign = src_callsign
        self.dst_callsign = dst_callsign
        self.expectAck = expectAck
        if ((self.expectAck == True) and (seq_num==None)): #if an ack is expected for this message and the seq_num passed in is the default
            self.seq_num = random.randint(0,127) #choose a number from 1 to 127
        elif ((self.expectAck == False) and (seq_num==None)):
            self.seq_num = 0
        else:
            self.seq_num = seq_num
        
    def getInfoString(self):
        fmt = 'SRC Callsign: [{0:s}], DST Callsign: [{1:s}], Ack?: {3:s}, sequence#: {4:s}, Message: {2:s}'
        return fmt.format(self.src_callsign, self.dst_callsign, self.msg_str.strip('\n'), str(self.expectAck), str(self.seq_num))
       
    def print(self):
        print(self.getInfoString())