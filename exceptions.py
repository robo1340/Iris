
class SquelchActive(Exception):
    pass
    
class IL2PHeaderDecodeError(Exception):
    pass
    
class NoCarrierDetectedError(Exception):
    pass

class NoBarkerCodeDetectedError(Exception):
    pass
    
class EndOfFrameDetected(Exception):
    pass
    
class ReceiverTimeout(Exception):
    pass