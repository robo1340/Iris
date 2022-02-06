
import numpy as np
import os
import pickle
import random
import string

def generate_callsign():
    #this array is used to randomly generate a callsign upon startup
    words = ['LADY','DEBT','POET','WOOD','GENE','EXAM','KING','BIRD','WEEK','CITY','ROAD', \
                  'OVEN','CELL','LOVE','GIRL','BATH','FOOD','DATA','HALL','MEAT','USER','SONG', \
                  'BUYER','BONUS','DRAMA','SALAD','POWER','PHOTO','TOPIC','UNION','MUSIC','UNCLE','NIGHT', \
                  'APPLE','GUEST','HEART','HONEY','PIANO','STORY','PIZZA','WOMAN','QUEEN','PHONE','OWNER', \
                  'CHILD','SHIRT','STEAK','ERROR','PAPER','HOTEL','ECHO','LIMA','SCENE','SKILL','BLOOD', \
                  'MIXED','BROAD','MACHO','TACKY','FRAIL','PIXY','FAIRY','SCHIZ','HEAVY','ANGRY','BASIC', \
                  'DUSTY','SHARP','SHORT','JOLLY','ACRID','SABLE','IRATE','BAWDY','DRUNK','NEEDY','NAIVE', \
                  'GIDDY','SASSY','RASPY','ROYAL','ROUND','SALTY','STALE','FREED','RIPE','WARY','FAST', \
                  'RUDE','TAME','PALE','MUTE','LEWD','KEEN','DEAR','ZANY','LAZY','SOUR','LUCH', \
                  'FAIR','POOR','SLOW','SEXY','DEAD','HURT','NEAT','ACID','GAMY','LOUD','UGLY']
    #return ''.join(random.choice(string.ascii_uppercase) for i in range(6))
    return random.choice(words) + str(random.randint(1,9))


##@brief configuration class
class Configuration:
    Fs = 8000.0  # sampling frequency [Hz]
    Tsym = 0.001  # symbol duration [seconds]
    Npoints = 2
    frequencies = [2000]  # use 1..8 kHz carriers

    # audio config
    bits_per_sample = 16
    latency = 0.1

    # sender config
    #carrier_length = 750 ##carrier length in milliseconds
    silence_start = 0.1
    silence_stop = 0.1

    # receiver config
    skip_start = 0.1
    timeout = 2.0 #timeout when looking for prefix symbols
    
    my_callsign = ''
    
    #randomly generate a callsign if the program is being started for the first time
    if os.path.isfile('./my_callsign_default.pickle'):
        with open('./my_callsign_default.pickle', 'rb') as f:
            my_callsign = pickle.load(f)
    else:
        my_callsign = generate_callsign()
        with open('./my_callsign_default.pickle', 'wb') as f:
            pickle.dump(my_callsign, f)
    
    dst_callsign = 'WAYWAX'
    
    gps_beacon_enable = True
    gps_beacon_period = 60
    carrier_length = 750
    enableForwarding = True
    enable_vibration = True
    hops = 1
    
    waypoint_beacon_enable = False
    waypoint_beacon_period = 60
    
    master_timeout = 20
    tx_cooldown = 1
    rx_cooldown = 5
    
    ackChecked = False
    autoScroll = True
        
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)

        self.sample_size = self.bits_per_sample // 8
        assert self.sample_size * 8 == self.bits_per_sample

        self.Ts = 1.0 / self.Fs
        self.Fsym = 1 / self.Tsym
        self.Nsym = int(self.Tsym / self.Ts) #the number of samples in one symbol
        self.baud = int(1.0 / self.Tsym)
        assert self.baud * self.Tsym == 1

        if len(self.frequencies) != 1:
            first, last = self.frequencies
            self.frequencies = np.arange(first, last + self.baud, self.baud)

        self.Nfreq = len(self.frequencies)
        self.carrier_index = 0
        self.Fc = self.frequencies[self.carrier_index]

        bits_per_symbol = int(np.log2(self.Npoints))
        assert 2 ** bits_per_symbol == self.Npoints
        self.bits_per_baud = bits_per_symbol * self.Nfreq
        self.modem_bps = self.baud * self.bits_per_baud
        self.carriers = np.array([
            np.exp(2j * np.pi * f * np.arange(0, self.Nsym) * self.Ts)
            for f in self.frequencies
        ])

        # QAM constellation
        Nx = 2 ** int(np.ceil(bits_per_symbol // 2))
        Ny = self.Npoints // Nx
        symbols = [complex(x, y) for x in range(Nx) for y in range(Ny)]
        symbols = np.array(symbols)
        symbols = symbols - symbols[-1]/2
        self.symbols = symbols / np.max(np.abs(symbols))
