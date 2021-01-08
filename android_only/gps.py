from plyer import gps
import logging

log = logging.getLogger('__name__')

class GPS():

    def __init__(self):
        self.current_location = None ##a dictionary containing the current lat, long, bearing, speed, altitude, etc.
        try:
            gps.configure(on_location=self.__on_location_update)
            self.start()
        except BaseException:
            log.error('No GPS detected on this device')
            #return None
        
    def __on_location_update(self, **kwargs):
        self.current_location = kwargs
        print('location updated')
        
        ## Decodificas the json
        #s = str(self.current_location)
        #print(s)

    def getLocation(self):
        return self.current_location
    
    def stop(self):
        gps.stop()
        
    def start(self):
        gps.start(minTime=5000, minDistance=0)