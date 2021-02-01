#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import itertools
import logging
import functools
import os
import sys
import io
import numpy as np
import threading
import time
import queue
import wave

from func_timeout import func_set_timeout, FunctionTimedOut

import pkg_resources
import async_reader
import audio
import common
from common import Status
import send as _send
import recv as _recv
import stream
import detect
import sampling
import exceptions

import config

import IL2P_API

master_timeout = 20 #sets the timeout for the last line of defense when the program is stuck
tx_cooldown = 1 #cooldown period after the sending in seconds, the program may not transmit for this period of time after transmitting a frame
rx_cooldown = 0.5 #cooldown period after receiving in seconds, the program may not receive or transmit for this period of time after receiving a frame

# Python 3 has `buffer` attribute for byte-based I/O
_stdin = getattr(sys.stdin, 'buffer', sys.stdin)
_stdout = getattr(sys.stdout, 'buffer', sys.stdout)

from kivy.logger import Logger as log

##@brief a class to cache the most recent status update so that the service does
## not needlessly transmit the same status update to the main application over
## and over again
class StatusUpdater():
    def __init__(self, service_controller):
        self.current_status = None
        self.service_controller = service_controller
        
    def update_status(self, new_status):
        if (new_status != self.current_status):
                self.service_controller.send_status(new_status)
                self.current_status = new_status
                
##@brief main program function to send frames
##@config Configuration object
##@src a stream of bytes to be sent
##@dst a stream to send bytes to
##@return returns true when src is sent successfully, returns false when an exception occurs
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
        sender.modulate(data)

        data_duration = sender.offset - training_duration
        log.info('Sent %.3f kB @ %.3f seconds', reader.total / 1e3, data_duration / Fs)

        sender.write(np.zeros(int(Fs * config.silence_stop))) # post-padding audio with silence
        return True
    except BaseException:
        log.warning('WARNING: the sender failed, message may have not been fully sent')
        return False

##@brief program loop to receive frames
##@config Configuration object
##@src input stream containing raw audio data
##@dst a ReceiverPipe object to place outgoing bytes after they have been decoded
##@stat_update a pointer to the StatusUpdater obejct
##@return returns 0 when no frame is received, returns -1 when an error occurs while receiving, returns 1 when frame was received successfully
@func_set_timeout(master_timeout)
def recv(config, src, dst, stat_update, service_controller):
    reader = stream.Reader(src, data_type=common.loads)
    signal = itertools.chain.from_iterable(reader)

    #pylab = pylab or common.Dummy()
    detector = detect.Detector(config=config, pylab=None)
    receiver = _recv.Receiver(config=config, pylab=None)
     
    try:
        log.debug('Waiting for carrier tone: %.1f kHz', config.Fc / 1e3)
        
        #now look for the carrier
        signal, amplitude, freq_error = detector.run(signal)
        stat_update.update_status(Status.SQUELCH_OPEN)

        service_controller.send_signal_strength(amplitude)
        
        freq = 1 / (1.0 + freq_error)  # receiver's compensated frequency
        gain = 1.0 / amplitude
        log.info('Gain correction: %.3f Frequency correction: %.3f ppm', gain, (freq - 1) * 1e6)

        sampler = sampling.Sampler(signal, sampling.defaultInterpolator, freq=freq)
        receiver.run(sampler, gain=1.0/amplitude, output=dst) #this method will keep running until an exception occurs

    except exceptions.EndOfFrameDetected: #the full frame was received
        if (dst.il2p.readFrame()):
            stat_update.update_status(Status.MESSAGE_RECEIVED)
            return 1
        else:
            stat_update.update_status(Status.SQUELCH_CLOSED)
            return -1
    except exceptions.IL2PHeaderDecodeError:
        log.warning('WARNING: failed when pre-emptively decoding frame header')
        stat_update.update_status(Status.SQUELCH_CLOSED)
        return -1
    except (exceptions.SquelchActive, exceptions.NoCarrierDetectedError): #exception is raised when the squelch is turned on
        stat_update.update_status(Status.SQUELCH_CLOSED)
        return 0
    except FunctionTimedOut:
        stat_update.update_status(Status.SQUELCH_CLOSED)
        print('\nERROR!:  receiver.run timed out\n')
        return -1
    except BaseException: 
        stat_update.update_status(Status.SQUELCH_CLOSED)
        log.exception('Decoding failed')
        return -1
    return 0
        
##@brief class used to pipe data to the link layer and tell it when the full packet has been received        
class ReceiverPipe():
    def __init__(self, il2p=None):
        self.recv_queue = queue.Queue(maxsize=IL2P_API.RAW_FRAME_MAXLEN) #queue containing received bytes in the order they were received
        self._full_frame_received = False
        self._squelchOpen = False
        
        self.il2p = il2p ##IL2P_API object
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
                self.header = self.il2p.engine.decode_header(self.raw_header, verbose=False)
                self.raw_payload_size = self.header.getRawPayloadSize()
                toReturn = (self.recv_cnt, self.raw_payload_size) #return bytes received and bytes remaining to be received
            except BaseException:
                #an error occurred while pre-emptively decoding the frame
                toReturn =(-1,-1)
            
        elif (self.header is not None):
            if (self.recv_cnt == self.raw_payload_size + IL2P_API.RAW_HEADER_LEN + IL2P_API.PREAMBLE_LEN): #if the full frame has been received
                self.header = None
                temp = self.recv_cnt
                self.recv_cnt = 0
                self.raw_header.fill(0)
                toReturn = (temp, 0)
            elif (self.recv_cnt > len(self.raw_header)): #if the header has been received but payload has not been completely received
                remaining = self.raw_payload_size - self.recv_cnt + IL2P_API.RAW_HEADER_LEN + IL2P_API.PREAMBLE_LEN
                toReturn = (self.recv_cnt, remaining)
        else: #the header has not been completely received
            toReturn = (self.recv_cnt, -1)
            
        return toReturn
    def reset(self):
        self.recv_cnt = 0
        self.header = None
        self.recv_queue.queue.clear()

def transceiver_func(args, service_controller, stats, il2p, ini_config, config):
    master_timeout = float(ini_config['MAIN']['master_timeout'])
    tx_cooldown = float(ini_config['MAIN']['tx_cooldown'])
    rx_cooldown = float(ini_config['MAIN']['rx_cooldown'])
    config.rx_timeout = int(ini_config['MAIN']['rx_timeout'])

    fmt = ('{0:.1f} kb/s ({1:d}-QAM x {2:d} carriers) Fs={3:.1f} kHz')
    description = fmt.format(config.modem_bps / 1e3, len(config.symbols), config.Nfreq, config.Fs / 1e3)
    log.info(description)

    def interface_factory():
        return args.interface
    
    AndroidMediaPlayer = None
    if (args.platform == common.Platform.ANDROID):
        #import wave
        from jnius import autoclass
        AndroidMediaPlayer = autoclass('android.media.MediaPlayer')
        
    link_layer_pipe = ReceiverPipe(il2p)
    args.recv_dst = link_layer_pipe
    il2p.reader.setSource(link_layer_pipe)
    
    most_recent_tx = 0 #the time of the most recent frame transmission
    most_recent_rx = 0 #the time of the most recent frame reception
    has_ellapsed = lambda start, duration : ((time.time() - start) > duration)
    
    stat_update = StatusUpdater(service_controller)
    
    with args.interface:
    #    args.interface.print_input_devices()
    
        while (service_controller.stopped() == False): #main transceiver loop, keep going so long as the service controller thread is running
        #while (threading.currentThread().stopped() == False) and (service_controller.stopped() == False): #main program loop for the receiver
            try:
                #sender args
                if (AndroidMediaPlayer is None):
                    output_opener = common.FileType('wb', interface_factory)
                    args.sender_dst = output_opener(args.output) #pipe the encoded symbols into the audio library

                input_opener = common.FileType('rb', interface_factory)
                args.recv_src = input_opener(args.input) #receive encoded symbols from the audio library

                ret_val = recv(config, src=args.recv_src, dst=args.recv_dst, stat_update=stat_update, service_controller=service_controller)
                if (ret_val == 1):
                    stats.rxs += 1
                    service_controller.send_statistic('rx_success',stats.rxs)
                    #time.sleep(rx_cooldown)
                    most_recent_rx = time.time()
                elif (ret_val == -1):
                    stats.rxf += 1
                    service_controller.send_statistic('rx_failure',stats.rxf)
                
                if ((il2p.isTransmissionPending() == True) and has_ellapsed(most_recent_tx,tx_cooldown) and has_ellapsed(most_recent_rx,rx_cooldown)): #get the next frame from the send queue
                    stat_update.update_status(Status.TRANSMITTING)
                    frame_to_send = il2p.getNextFrameToTransmit()
                    if (frame_to_send == None):
                        continue
                    args.sender_src = io.BytesIO(frame_to_send) #pipe the input string into the sender
                    
                    #save to an intermediate file if this is android
                    if (AndroidMediaPlayer is not None):
                        args.sender_dst = open('temp.pcm','wb')
                    
                    #push the data to args.sender_dst
                    if (send(config, src=args.sender_src, dst=args.sender_dst)):
                        stats.txs += 1
                        service_controller.send_statistic('tx_success',stats.txs)
                    else:
                        stats.txf += 1
                        service_controller.send_statistic('tx_failure',stats.txf)  

                    #convert the intermediate pcm file to a wav file and play it with a java class
                    if (AndroidMediaPlayer is not None):
                        args.sender_dst.close()   
                        with open('temp.pcm', 'rb') as pcmfile:
                            pcmdata = pcmfile.read()
                        with wave.open('temp.wav', 'wb') as wavfile:
                            wavfile.setparams((1, 2, 8000, 0, 'NONE', 'NONE'))
                            wavfile.writeframes(pcmdata)
                            
                        mPlayer = AndroidMediaPlayer()
                        mPlayer.setDataSource('temp.wav')
                        mPlayer.prepare()
                        #print(mPlayer.getDuration())
                        mPlayer.start()
                        time.sleep(mPlayer.getDuration()*1.0/1000)#mPlayer.getDuration is in milliseconds
                        mPlayer.release()
                    
                    most_recent_tx = time.time()
                    stat_update.update_status(Status.SQUELCH_CLOSED)
                else:
                    time.sleep(0)
            except FunctionTimedOut:
                log.error('\nERROR!:  recv or send timed out\n')
            #except:
            #    print('uncaught exception or keyboard interrupt')
            finally:
                if args.recv_src is not None:
                    args.recv_src.close()
                if args.sender_src is not None:
                    args.sender_src.close()
                if args.sender_dst is not None:
                    args.sender_dst.close()

        #end of main while loop
        if args.recv_src is not None:
            args.recv_src.close()
        if args.sender_src is not None:
            args.sender_src.close()
        if args.sender_dst is not None:
            args.sender_dst.close()
        log.info('Transceiver Thread shutting down')  