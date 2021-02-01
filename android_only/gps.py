
from plyer import gps
import logging

log = logging.getLogger('__name__')

class GPS():

    def __init__(self):
        self.current_location = None ##a dictionary containing the current lat, long, bearing, speed, altitude, etc.
        self.service_controller = None
        
    def __on_location_update(self, **kwargs):
        if (self.current_location == None):
            self.service_controller.send_gps_lock_achieved(True) #tell the UI that a gps lock has been achieved
        #what kwargs looks like
        #{'lat': 37.57422971, 'lon': -97.24803824, 'speed': 0.0, 'bearing': 0.0, 'altitude': 379.0, 'accuracy': 19.296001434326172}
        #remove entries we aren't interested in
        kwargs.pop('speed')
        kwargs.pop('bearing')
        kwargs.pop('accuracy')
        #print(kwargs)
        
        self.current_location = kwargs
        
        ## Decodificas the json
        #s = str(self.current_location)
        #print(s)

    def getLocation(self):
        return self.current_location
    
    def stop(self):
        gps.stop()
    
    ##@brief start the GPS logger
    ##@param service_controller a class of type ServiceController that will be sending gps coordinates to the UI
    def start(self, service_controller):
        self.service_controller = service_controller
        try:
            gps.configure(on_location=self.__on_location_update)
            gps.start(minTime=5000, minDistance=0)
        except BaseException:
            log.error('No GPS detected on this device')

'''
      
# import needed modules
import android
import time
import sys, select, os #for loop exit

#Initiate android-module
droid = android.Android()
class GPS():

    def __init__(self):

        print("start gps-sensor...")
        droid.startLocating()

        while True:
            #exit loop hook
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = input()
                print("exit endless loop...")
                break

            #wait for location-event
            event = droid.eventWaitFor('location',10000).result
            if event['name'] == "location":
                try:
                    #try to get gps location data
                    timestamp = repr(event['data']['gps']['time'])
                    longitude = repr(event['data']['gps']['longitude'])
                    latitude = repr(event['data']['gps']['latitude'])
                    altitude = repr(event['data']['gps']['altitude'])
                    speed = repr(event['data']['gps']['speed'])
                    accuracy = repr(event['data']['gps']['accuracy'])
                    loctype = "gps"
                except KeyError:
                    #if no gps data, get the network location instead (inaccurate)
                    timestamp = repr(event['data']['network']['time'])
                    longitude = repr(event['data']['network']['longitude'])
                    latitude = repr(event['data']['network']['latitude'])
                    altitude = repr(event['data']['network']['altitude'])
                    speed = repr(event['data']['network']['speed'])
                    accuracy = repr(event['data']['network']['accuracy'])
                    loctype = "net"

                data = loctype + ";" + timestamp + ";" + longitude + ";" + latitude + ";" + altitude + ";" + speed + ";" + accuracy

            print(data) #logging
            time.sleep(5) #wait for 5 seconds

        print("stop gps-sensor...")
        droid.stopLocating()
        '''