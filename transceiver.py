#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
#import argparse
import logging
import os
import sys
import io
import numpy as np
import threading
import time

from func_timeout import func_set_timeout, FunctionTimedOut

import pkg_resources
import async_reader
import audio
import main
import common
from common import Status

import IL2P_API
import IL2P

import config

# Python 3 has `buffer` attribute for byte-based I/O
_stdin = getattr(sys.stdin, 'buffer', sys.stdin)
_stdout = getattr(sys.stdout, 'buffer', sys.stdout)

log = logging.getLogger('__name__')

config = config.main_config

def chat_transceiver_func(args, stats, msg_send_queue, msg_receive_queue):
    fmt = ('{0:.1f} kb/s ({1:d}-QAM x {2:d} carriers) Fs={3:.1f} kHz')
    description = fmt.format(config.modem_bps / 1e3, len(config.symbols), config.Nfreq, config.Fs / 1e3)
    log.info(description)

    def interface_factory():
        return args.interface
    
    #frame writer used by the sender
    frame_writer = IL2P_API.IL2P_Frame_Writer(verbose=True)
    
    #frame reader used by the receiver
    frame_reader = IL2P_API.IL2P_Frame_Reader(verbose=True, msg_output_queue=msg_receive_queue)
    link_layer_pipe = main.ReceiverPipe(frame_reader)
    
    config.squelch = 0.1 #hardcode the squelch for now
    args.recv_dst = link_layer_pipe
    frame_reader.setSource(link_layer_pipe)
    
    
    while (threading.currentThread().stopped() == False): #main program loop for the receiver
        with args.interface:
            try:
                #sender args
                output_opener = common.FileType('wb', interface_factory)
                args.sender_dst = output_opener(args.output) #pipe the encoded symbols into the audio library

                input_opener = common.FileType('rb', interface_factory)
                args.recv_src = input_opener(args.input) #receive encoded symbols from the audio library

                ret_val = main.recv(config, src=args.recv_src, dst=args.recv_dst, ui=args.ui, pylab=None)
                if (ret_val == 1):
                    stats.rxs += 1
                    args.ui.update_rx_success_cnt(stats.rxs)
                elif (ret_val == -1):
                    stats.rxf += 1
                    args.ui.update_rx_failure_cnt(stats.rxf)
                
                if (msg_send_queue.empty() == False): #get the next frame from the send queue
                    args.ui.updateStatusIndicator(Status.TRANSMITTING)
                    msg = msg_send_queue.get()
                    frame_to_send = frame_writer.getFrameFromTextMessage(msg.msg_str, msg.src_callsign, msg.dst_callsign, msg.expectAck, msg.seq_num)
                    args.sender_src = io.BytesIO(frame_to_send) #pipe the input string into the sender
                    
                    if (main.send(config, src=args.sender_src, dst=args.sender_dst)):
                        stats.txs += 1
                        args.ui.update_tx_success_cnt(stats.txs)
                    else:
                        stats.txf += 1
                        args.ui.update_tx_failure_cnt(stats.txf)
                    args.ui.updateStatusIndicator(Status.SQUELCH_OPEN)
                    time.sleep(1) #sleep for just a bit after transmitting
                else:
                    time.sleep(0)
            except FunctionTimedOut:
                print('\nERROR!:  main.recv or main.send timed out\n')
            except:
                print('uncaught exception or keyboard interrupt')
            finally:
                if args.recv_src is not None:
                    args.recv_src.close()
                if args.sender_src is not None:
                    args.sender_src.close()
                if args.sender_dst is not None:
                    args.sender_dst.close()
                log.debug('Finished I/O')   
    
