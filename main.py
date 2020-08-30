import itertools
import logging
import functools
import threading
import time
import queue

import numpy as np
from func_timeout import func_set_timeout, FunctionTimedOut

import send as _send
import recv as _recv
import common
import stream
import detect
import sampling
import exceptions
from common import Status

import IL2P_API

log = logging.getLogger(__name__)

master_timeout = 20 #sets the timeout for the last line of defense when the program is stuck
   
def encode_to_bits(data, framer=None):
    converter = common.BitPacker()
    for frame in common.iterate(data=data, size=50, func=bytearray, truncate=False):
        for byte in frame:
            #print (converter.to_bits[byte])
            yield converter.to_bits[byte]

@func_set_timeout(master_timeout)
def send(config, src, dst):    
    sender = _send.Sender(dst, config=config)
    Fs = config.Fs

    try: 
        sender.write(np.zeros(int(Fs * (config.silence_start)))) # pre-padding audio with silence (priming the audio sending queue)

        sender.start()

        training_duration = sender.offset
        log.debug('Sending %.3f seconds of training audio', training_duration / Fs)

        reader = stream.Reader(src, eof=True)
        data = itertools.chain.from_iterable(reader)
        bits = itertools.chain.from_iterable(encode_to_bits(data))
        sender.modulate(bits=bits)

        data_duration = sender.offset - training_duration
        log.info('Sent %.3f kB @ %.3f seconds', reader.total / 1e3, data_duration / Fs)

        sender.write(np.zeros(int(Fs * config.silence_stop))) # post-padding audio with silence
        return True
    except BaseException:
        log.warning('WARNING: the sender failed, message may have not been fully sent')
        return False

##@brief main program loop to receive IL2P packets
##@config Configuration object
##@src input stream containing raw audio data
##@dst a ReceiverPipe object to place outgoing bytes after they have been decoded
##@ui a pointer to the ui object
##@return returns 0 when no frame is received, returns -1 when an error occurs while receiving, returns 1 when frame was received successfully
@func_set_timeout(master_timeout)
def recv(config, src, dst, ui, pylab=None):
    reader = stream.Reader(src, data_type=common.loads)
    signal = itertools.chain.from_iterable(reader)

    pylab = pylab or common.Dummy()
    detector = detect.Detector(config=config, pylab=pylab)
    receiver = _recv.Receiver(config=config, pylab=pylab)
     
    try:
        log.debug('Waiting for carrier tone: %.1f kHz', config.Fc / 1e3)
        
        #this function will only return once a signal above the squelch threshhold has been detected
        signal = detector.detect_signal(signal, config.squelch, config.squelch_timeout) 
        ui.updateStatusIndicator(Status.SQUELCH_OPEN)
        
        #now look for the carrier
        signal, amplitude, freq_error = detector.run(signal)

        freq = 1 / (1.0 + freq_error)  # receiver's compensated frequency
        gain = 1.0 / amplitude
        log.debug('Gain correction: %.3f Frequency correction: %.3f ppm', gain, (freq - 1) * 1e6)

        sampler = sampling.Sampler(signal, sampling.defaultInterpolator, freq=freq)
        receiver.run(sampler, gain=1.0/amplitude, output=dst) #this method will keep running until an exception occurs

    except exceptions.EndOfFrameDetected: #the full frame was received
        ui.updateStatusIndicator(Status.MESSAGE_RECEIVED)
        if (dst.frame_reader.readFrame()):
            return 1
        else:
            return -1
    except exceptions.IL2PHeaderDecodeError:
        log.warning('WARNING: failed when pre-emptively decoding frame header')
        ui.updateStatusIndicator(Status.SQUELCH_CLOSED)
        return -1
    except (exceptions.SquelchActive, exceptions.NoCarrierDetectedError): #exception is raised when the squelch is turned on
        ui.updateStatusIndicator(Status.SQUELCH_CLOSED)
        return 0
    except FunctionTimedOut:
        ui.updateStatusIndicator(Status.SQUELCH_CLOSED)
        print('\nERROR!:  receiver.run timed out\n')
        return -1
    except BaseException: 
        ui.updateStatusIndicator(Status.SQUELCH_CLOSED)
        log.exception('Decoding failed')
        return -1
    return 0
        
##@brief class used to pipe data to the link layer and tell it when the full packet has been received        
class ReceiverPipe():
    def __init__(self, frame_reader=None):
        self.recv_queue = queue.Queue(maxsize=IL2P_API.RAW_FRAME_MAXLEN)
        self._full_frame_received = False
        self._squelchOpen = False
        
        self.frame_reader = frame_reader ##IL2P_Frame_Reader object
        self.raw_header = np.zeros(IL2P_API.RAW_HEADER_LEN + IL2P_API.PREAMBLE_LEN, dtype=np.uint8) ##a header plus the preamble byte
        self.header = None ##will hold an IL2P_Frame_Header object
        self.recv_cnt = 0
        self.raw_payload_size = 0
        
    ##@brief add a new byte to the receive queue. When the header is received, it will be decoded so that the number of bytes in the payload can be known
    ##@param b the new byte to be added to the queue
    ##@return returns a tuple of 2 values of the form (int, int)
    ##  The first integer value gives the number of bytes that have been added to the queue
    ##  The second integer gives the number of remaining bytes to be received until the frame ends, note this value won't be known until the header is received and decoded, until then this value will be -1
    ##@throws IL2P_Header_Decode_Error
    def addByte(self, b):
        self.recv_cnt += 1
        self.recv_queue.put(b)
        if (self.recv_cnt <= len(self.raw_header)):
            self.raw_header[self.recv_cnt-1] = b
        
        if (self.recv_cnt == len(self.raw_header)): #if the full header has been received
            try:
                self.header = self.frame_reader.frame_engine.decode_header(self.raw_header)
                self.raw_payload_size = self.header.getRawPayloadSize()
                return (self.recv_cnt, self.raw_payload_size) #return bytes received and bytes remaining to be received
            except BaseException:
                #an error occurred while pre-emptively decoding the frame
                return(-1,-1)
            
        elif (self.header is not None):
            if (self.recv_cnt == self.raw_payload_size + IL2P_API.RAW_HEADER_LEN + IL2P_API.PREAMBLE_LEN): #if the full frame has been received
                self.header = None
                temp = self.recv_cnt
                self.recv_cnt = 0
                self.raw_header.fill(0)
                return (temp, 0)
            elif (self.recv_cnt > len(self.raw_header)): #if the header has been received but payload has not been completely received
                remaining = self.raw_payload_size - self.recv_cnt + IL2P_API.RAW_HEADER_LEN + IL2P_API.PREAMBLE_LEN
                return (self.recv_cnt, remaining)
        else: #the header has not been completely received
            return (self.recv_cnt, -1)
            
    def reset(self):
        self.recv_cnt = 0
        with self.recv_queue.mutex:
            self.recv_queue.queue.clear()
        

