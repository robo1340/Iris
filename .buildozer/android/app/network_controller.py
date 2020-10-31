import threading
import time
import random
import logging
import queue
import random
import time
import sys
from datetime import datetime

log = logging.getLogger('__name__')

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer


def print_handler(address, *args):
    print(args[0])
    print(args[1])
    print(args[2])


def default_handler(address, *args):
    print(f"DEFAULT {address}: {args}")

def network_controller_func(arg=None):
    while (threading.currentThread().stopped() == False):
        dispatcher = Dispatcher()
        dispatcher.map("/test", print_handler)
        dispatcher.set_default_handler(default_handler)
        
        ip = "127.0.0.1"
        port = 1337

        server = BlockingOSCUDPServer((ip, port), dispatcher)
        server.serve_forever()  # Blocks forever
