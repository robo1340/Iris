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
import math

from func_timeout import func_set_timeout, FunctionTimedOut

from jnius import autoclass
from jnius import cast

import pkg_resources
#import async_reader
import audio
import common
import send as _send
import recv as _recv
import stream
import detect
import exceptions

import config

import IL2P_API

master_timeout = 30 #sets the timeout for the last line of defense when the program is stuck

from kivy.logger import Logger as log

class Cooldown():
    def __init__(self, base_cooldown, vary):
        self.base_cooldown = base_cooldown
        self.vary = vary
        self.cooldown = self.base_cooldown
        
    def get(self):
        self.cooldown = self.base_cooldown + np.random.uniform(0,self.vary)*self.base_cooldown
        return self.cooldown

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

##@brief a Carrier Sense Multiple Access Controller
class CSMA_Controller():
    def __init__(self, service_controller):
        self.service_controller = service_controller
        
        
    ##@brief feed a new value to the CSMA Controller
    ##send a new message to the view_controller with the new channel noise estimate
    ##@return return True when the channel is clear, return False otherwise
    def feedNewValue(self, mean_abs_value):
        log_val = 10*np.log10(mean_abs_value)
        if (not np.isfinite(log_val)):
            return False
        self.service_controller.send_signal_strength(log_val)
        return False
                
##@brief method to write link layer frames into audio data
##@config Configuration object
##@src a stream of bytes to be sent
##@dst a stream to send bytes to
##@param carrier_length specifies the carrier length (in milliseconds) to use
##@return returns true when src is sent successfully, returns false when an exception occurs
@func_set_timeout(master_timeout)
def send(config, src, dst, carrier_length):    
    sender = _send.Sender(dst, config=config, carrier_length=carrier_length)
    Fs = config.Fs

    #try: 
    sender.write(np.zeros(int(Fs * (config.silence_start)))) # pre-padding audio with silence (priming the audio sending queue)

    sender.start()

    #training_duration = sender.offset
    #log.debug('Sending %.3f seconds of training audio', training_duration / Fs)

    reader = stream.Reader(src, eof=True)
    data = itertools.chain.from_iterable(reader)
    sender.modulate(data)

    log.debug('Sent %.3f kB @ %.3f seconds', reader.total / 1e3, sender.offset / Fs)

    sender.write(np.zeros(int(Fs * config.silence_stop))) # post-padding audio with silence
    #log.info('sender complete')
    return True 
    #except BaseException:
    #    log.warning('WARNING: the sender failed, message may have not been fully sent')
    #    return False

##@brief method that uses android.media.MediaPlayer to play a .pcm audio file
##@param player an Android Media Player instance
##@param pcmFileName the name of the file to be played, example 'temp.pcm'
def playAudioData(player, pcmFileName):
    wavFileName = pcmFileName.split('.')[0] + '.wav'
    with open(pcmFileName, 'rb') as pcmfile:
        pcmdata = pcmfile.read()
    with wave.open(wavFileName, 'wb') as wavfile:
        wavfile.setparams((1, 2, 8000, 0, 'NONE', 'NONE'))
        wavfile.writeframes(pcmdata)        
    
    player.setDataSource(wavFileName)
    player.prepare()
    player.start()
    time.sleep(player.getDuration()*1.0/1000)#mPlayer.getDuration is in milliseconds
    player.reset()

    
##@brief program loop to receive frames
##@config Configuration object
##@signal input stream containing raw audio data
##@dst a ReceiverPipe object to place outgoing bytes after they have been decoded
##@stat_update a pointer to the StatusUpdater obejct
##@return returns 0 when no frame is received, returns -1 when an error occurs while receiving, returns 1 when frame was received successfully
@func_set_timeout(master_timeout)
def recv(detector, receiver, signal, dst, stat_update, service_controller):
    try:
        log.debug('Waiting for carrier tone')
        
        #now look for the carrier
        gain = detector.run(signal,stat_update)
        if (gain < 0): #if the program gets here, a carrier was detected but no barker code was found thereafter
            raise exceptions.NoBarkerCodeDetectedError
        
        stat_update.update_status(common.SQUELCH_OPEN)
            
        #service_controller.send_signal_strength(1.0/gain)
        
        log.debug('Gain correction: %.3f', gain)

        receiver.run(signal, gain=gain, output=dst) #this method will keep running until an exception occurs

    except exceptions.EndOfFrameDetected: #the full frame was received
        if (dst.il2p.readFrame()):
            stat_update.update_status(common.MESSAGE_RECEIVED)
            return 1
        else:
            return -1
    except exceptions.IL2PHeaderDecodeError:
        log.warning('WARNING: failed when pre-emptively decoding frame header')
        return -1
    except (exceptions.SquelchActive, exceptions.NoCarrierDetectedError): #exception is raised when the squelch is turned on
        return 0
    except (exceptions.NoBarkerCodeDetectedError): #exception is raised when carrier is detected but no susequent barker code is
        return 0
    except FunctionTimedOut:
        log.error('\nERROR!:  receiver.run timed out\n')
        return -1
    except BaseException: 
        log.exception('Decoding failed')
        return -1
    return 0


##@brief class used to pipe data to the link layer and tell it when the full packet has been received        
class ReceiverPipe():
    def __init__(self, il2p=None):
        self.recv_queue = queue.Queue(maxsize=IL2P_API.RAW_FRAME_MAXLEN) #queue containing received bytes in the order they were received
        #self._full_frame_received = False
        #self._squelchOpen = False
        
        self.il2p = il2p ##IL2P_API object
        self.raw_header = np.zeros(IL2P_API.RAW_HEADER_LEN, dtype=np.uint8) ##a header plus the preamble byte
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
            if (self.recv_cnt == self.raw_payload_size + IL2P_API.RAW_HEADER_LEN): #if the full frame has been received
                self.header = None
                temp = self.recv_cnt
                self.recv_cnt = 0
                self.raw_header.fill(0)
                toReturn = (temp, 0)
            elif (self.recv_cnt > len(self.raw_header)): #if the header has been received but payload has not been completely received
                remaining = self.raw_payload_size - self.recv_cnt + IL2P_API.RAW_HEADER_LEN
                toReturn = (self.recv_cnt, remaining)
        else: #the header has not been completely received
            toReturn = (self.recv_cnt, -1)
            
        return toReturn
    def reset(self):
        self.recv_cnt = 0
        self.header = None
        self.recv_queue.queue.clear()

def setAudioOutputRadio(manager, AudioManager):
    manager.setMode(AudioManager.MODE_NORMAL)
    manager.setSpeakerphoneOn(False)
    manager.setMicrophoneMute(False)
    
def setAudioOutputSpeaker(manager, AudioManager):
    #MODE_IN_CALL
    #MODE_IN_COMMUNICATION
    manager.setMode(AudioManager.MODE_IN_COMMUNICATION)
    manager.setSpeakerphoneOn(True)
    manager.setMicrophoneMute(True)
        
def transceiver_func(args, service_controller, stats, il2p, config):
    master_timeout = config.master_timeout
    tx_cooldown = config.tx_cooldown
    base_rx_cooldown = config.rx_cooldown
    
    log.info("tx/rx cooldown: %f/%f\n" % (tx_cooldown,base_rx_cooldown))
    rx_cooldown_randomizer = Cooldown(base_rx_cooldown, 0.3)
    rx_cooldown = rx_cooldown_randomizer.get()

    fmt = ('{0:.1f} kb/s ({1:d}-QAM x {2:d} carriers) Fs={3:.1f} kHz')
    description = fmt.format(config.modem_bps / 1e3, len(config.symbols), config.Nfreq, config.Fs / 1e3)
    log.info(description)

    def interface_factory():
        return args.interface
    
    AndroidMediaPlayer = None
    AudioManager = None
    if (args.platform == common.Platform.ANDROID):
        AndroidMediaPlayer = autoclass('android.media.MediaPlayer')
        AudioManager = autoclass('android.media.AudioManager')
    
    mplayer = AndroidMediaPlayer()
    '''
    log.info('Trying to do audio things')
    
    PythonService = autoclass("org.kivy.android.PythonService")
    activity = cast("android.app.Service", PythonService.mService)
    context = cast('android.content.Context', activity.getApplicationContext())
    audioManager = context.getSystemService(autoclass('android.content.Context').AUDIO_SERVICE)
    
    log.info('Did audio things')
    '''
    
    #setAudioOutputRadio(audioManager, AudioManager)

    link_layer_pipe = ReceiverPipe(il2p)
    args.recv_dst = link_layer_pipe
    il2p.reader.setSource(link_layer_pipe)
    
    csma = CSMA_Controller(service_controller)
    
    most_recent_tx = 0 #the time of the most recent frame transmission
    most_recent_rx = 0 #the time of the most recent frame reception
    has_ellapsed = lambda start, duration : ((time.time() - start) > duration)
    
    stat_update = StatusUpdater(service_controller)
    
    while (service_controller.stopped() == False):

        with args.interface:
        #    args.interface.print_input_devices()

            #receiver objects
            detector = detect.Detector(config=config)
            receiver = _recv.Receiver(config=config)

            #input_opener = common.FileType('rb', interface_factory)
            #args.recv_src = input_opener(args.input) #receive data from the audio library
            args.recv_src = common.audioOpener('rb', interface_factory, csma.feedNewValue)
            reader = stream.Reader(args.recv_src, data_type=common.loads)
            signal = itertools.chain.from_iterable(reader)

            #####################################################################

            while (service_controller.stopped() == False): #main transceiver loop, keep going so long as the service controller thread is running
                try:

                    ret_val = recv(detector, receiver, signal, args.recv_dst, stat_update, service_controller)

                    if (ret_val == 1):
                        stats.rxs += 1
                        service_controller.send_statistic('rx_success',stats.rxs)
                        most_recent_rx = time.time()
                    elif (ret_val == -1):
                        stats.rxf += 1
                        service_controller.send_statistic('rx_failure',stats.rxf)
                        most_recent_rx = time.time()
                    else:
                        if ((il2p.isTransmissionPending() == True) and has_ellapsed(most_recent_tx,tx_cooldown) and has_ellapsed(most_recent_rx,rx_cooldown)): #get the next frame from the send queue
                            rx_cooldown = rx_cooldown_randomizer.get()
                            frame_to_send, carrier_length = il2p.getNextFrameToTransmit()
                            if (frame_to_send == None):
                                continue
                            stat_update.update_status(common.TRANSMITTING)
                            args.sender_src = io.BytesIO(frame_to_send) #pipe the input string into the sender

                            #save to an intermediate file if this is android
                            if (AndroidMediaPlayer is not None):
                                args.sender_dst = open('temp.pcm','wb')

                            #push the data to args.sender_dst
                            if (send(config, src=args.sender_src, dst=args.sender_dst, carrier_length=carrier_length)):

                                stats.txs += 1
                                service_controller.send_statistic('tx_success',stats.txs)

                                #mplayer = AndroidMediaPlayer()
                                #convert the intermediate pcm file to a wav file and play it with a java class
                                args.sender_dst.close()   
                                playAudioData(mplayer,'temp.pcm')
                                
                            else:
                                stats.txf += 1
                                service_controller.send_statistic('tx_failure',stats.txf)  
                            most_recent_tx = time.time()
                        else:
                            time.sleep(0)
                except FunctionTimedOut:
                    log.error('\nERROR!:  recv or send timed out\n')
                #except:
                #    print('uncaught exception or keyboard interrupt')
                finally:
                    if mplayer is not None:
                        mplayer.reset()
                    #if args.recv_src is not None:
                    #    args.recv_src.close()
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
                
    #end of recovery loop
    log.info('Transceiver Thread shutting down')  
