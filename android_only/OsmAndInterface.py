from jnius import cast
from jnius import autoclass
#from jnius import PythonJavaClass, java_method

import time
import os
from datetime import datetime
import threading
import pickle

from kivy.logger import Logger as log

CONTACT_CATEGORY = 'Iris Contacts'

OSM_COLORS = ["blue", "red", "green", "brown", "orange", "yellow", "lightblue", "lightgreen", "purple", "pink"]

CONTACTS_FILE_NAME = 'contacts.pickle'

class ContactPoint():
    def __init__(self,callsign,lat,lon,time,index):
        self.callsign = callsign
        self.lat = lat
        self.lon = lon
        self.time = time
        self.index = index ##the index determining which color the ContactPoint will be in OsmAnd
        self.__name = self.callsign + ' | ' + datetime.now().strftime("%H:%M:%S")
        
    def getCurrentName(self):
        return self.__name
    
    def getNewName(self):
        self.__name = self.callsign + ' | ' + datetime.now().strftime("%H:%M:%S")
        self.time = time.time()
        return self.__name

class OsmAndInterface():

    def __init__(self):
        if os.path.isfile('./' + CONTACTS_FILE_NAME):
            with open(CONTACTS_FILE_NAME, 'rb') as f:
                self.contact_points_dict = pickle.load(f)
        else:
            self.contact_points_dict = {} #a dictionary describing the current contact points that have been placed
        
        #log.info(self.contact_points_dict)
        
        #keys are the callsign string, values are a tuple are objects of type ContactPoint
        self.started = False
        self.start()
            
    def isStarted(self):
        return self.started
    
    def start(self):
        try:
            OsmAPI = autoclass('main.java.net.osmand.osmandapidemo.OsmAndAidlHelper')

            '''
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            #currentActivity = PythonActivity.mActivity
            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            #application = currentActivity.getApplication()
            '''

            PythonService = autoclass("org.kivy.android.PythonService")
            activity = cast("android.app.Service", PythonService.mService)
            application = activity.getApplication()

            self.api = OsmAPI(application) #,None)

            time.sleep(1)
            self.refreshContacts()
            #self.clearContacts() 

            log.info('OsmAnd API Init Success')
            self.started = True
            return True
        except BaseException:
            log.error('OsmAnd was not detected on this device')
            threading.Timer(30, self.start).start()
            return False       
    
    ##@brief place a favorite marker in osmand representing the location of a radio contact
    ## that sent GPS coordinates. If the contact has been made previously, update the location of the
    ## favorite marker with the latest coordinates
    ##@param lat the latitude sent by the contact as a float
    ##@param lon the longitude sent by the contact as a float
    ##@param callsign the callsign of the contact
    ##@param description the description to be added to the favorites marker, this should be a
    ##  formatted string containing things like the time the contact was made
    def placeContact(self, lat, lon, callsign='', description=''):
        log.info('Placing contact')
        try:
            self.clearContacts()
            if callsign in self.contact_points_dict:
                pt = self.contact_points_dict[callsign]
                pt.getNewName()
                pt.lat = lat
                pt.lon = lon
            else:
                pt = ContactPoint(callsign, lat, lon, time.time(), (len(self.contact_points_dict) % len(OSM_COLORS)) )
                self.contact_points_dict[callsign] = pt

            self.populateContacts()
            self.saveContacts()
        except BaseException:
            log.error('An exception occurred while placing/updating a favorites marker in OsmAnd')

    def refreshContacts(self):
        self.clearContacts()
        self.populateContacts()
    
    def populateContacts(self):
        try:
            for callsign, pt in self.contact_points_dict.items():
                self.api.addFavorite(pt.lat, pt.lon, pt.getCurrentName(), '', '', CONTACT_CATEGORY, OSM_COLORS[pt.index], True) 
                #self.api.addFavorite(pt.lat, pt.lon, pt.getCurrentName(), description, '', CONTACT_CATEGORY, OSM_COLORS[pt.index], True)  
        except BaseException:
            log.error('An exception occurred while populating contacts in OsmAnd')        
    
    
    def saveContacts(self):
        with open(CONTACTS_FILE_NAME, 'wb') as f:
            pickle.dump(self.contact_points_dict, f)
    
    def eraseContacts(self):
        self.clearContacts()
        self.contact_points_dict.clear()
        self.saveContacts()
    
    ##@brief remove all contact markers that are in OsmAnd
    def clearContacts(self):
        try:
            for callsign, pt in self.contact_points_dict.items():
                self.api.removeFavorite(pt.lat, pt.lon, pt.getCurrentName(), CONTACT_CATEGORY)
            #self.api.removeFavoriteGroup(CONTACT_CATEGORY)
        except BaseException:
            log.error('An exception occurred while deleting a favorites marker in OsmAnd')

'''
osm.placeContact(35.0078, -97.0929, '000001', str(time.time()))
osm.placeContact(35.0088, -97.0929, '000002', str(time.time()))
osm.placeContact(35.0098, -97.0929, '000003', str(time.time()))
osm.placeContact(35.0108, -97.0929, '000004', str(time.time()))
osm.placeContact(35.0118, -97.0929, '000005', str(time.time()))
osm.placeContact(35.0128, -97.0929, '000006', str(time.time()))
osm.placeContact(35.0138, -97.0929, '000007', str(time.time()))
osm.placeContact(35.0148, -97.0929, '000008', str(time.time()))
osm.placeContact(35.0158, -97.0929, '000009', str(time.time()))
osm.placeContact(35.0168, -97.0929, '000010', str(time.time()))
osm.placeContact(35.0178, -97.0929, '000011', str(time.time()))
'''
#osm.clearContacts()













       