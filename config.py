import numpy as np
    
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
    
     #   properties = ['my_callsign', 'dst_callsign', 'ack_retries', 'ack_timeout', 'tx_cooldown', 
     #             'rx_cooldown', 'rx_timeout', 'ack', 'clear', 'scroll', 'master_timeout', 
     #             'Fs', 'Npoints', 'carrier_frequency', 'min_wait', 'max_wait']

    my_callsign = 'BAYWAX'
    dst_callsign = 'WAYWAX'
    
    gps_beacon_enable = False
    gps_beacon_period = 60
    carrier_length = 750
    
    master_timeout = 20
    tx_cooldown = 1
    rx_cooldown = 5
    
    ackChecked = False
    clearOnSend = True
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

'''
bitrates = {
    1: Configuration(Fs=8e3, Npoints=2, frequencies=[2e3]),
    2: Configuration(Fs=8e3, Npoints=4, frequencies=[2e3]),
    4: Configuration(Fs=8e3, Npoints=16, frequencies=[2e3]),
    12: Configuration(Fs=16e3, Npoints=16, frequencies=[3e3, 5e3]),
    42: Configuration(Fs=32e3, Npoints=64, frequencies=[4e3, 10e3]),
    80: Configuration(Fs=32e3, Npoints=256, frequencies=[2e3, 11e3]),
}'''
