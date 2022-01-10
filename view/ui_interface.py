import abc

class UI_Interface(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'load_data_source') and 
                callable(subclass.load_data_source) and 
                hasattr(subclass, 'extract_text') and 
                callable(subclass.extract_text) or 
                NotImplemented)

    # @abc.abstractmethod
    # def load_data_source(self, path: str, file_name: str):
        # """Load in the data set"""
        # raise NotImplementedError

    ##@brief add a new message label to the main scroll panel on the gui
    ##@param text_msg A TextMessageObject containing the received message
    @abc.abstractmethod
    def addMessageToUI(self, text_msg):
        raise NotImplementedError
    
    ##@brief look through the current messages displayed on the ui and delete any that have an ack_key matching the ack_key passed in
    ##@ack_key, a tuple of src, dst, and sequence number forming an ack of messages to delete
    @abc.abstractmethod
    def addAckToUI(self, ack_key):
        raise NotImplementedError
        
    @abc.abstractmethod
    def updateStatusIndicator(self, status):
        raise NotImplementedError
    
    @abc.abstractmethod
    def clearReceivedMessages(self):
        raise NotImplementedError
    
    @abc.abstractmethod
    def isAckChecked(self):
        raise NotImplementedError
        
    @abc.abstractmethod
    def isGPSTxChecked(self):
        raise NotImplementedError
        
    @abc.abstractmethod
    def isGPSTxOneShotChecked(self):
        raise NotImplementedError
        
    @abc.abstractmethod
    def getGPSBeaconPeriod(self):
        raise NotImplementedError
    
    @abc.abstractmethod    
    def update_my_displayed_location(self, gps_dict):
        raise NotImplementedError
        
    ##@brief add a new gps message label to the gps scroll panel on the gui
    ##@param gps_msg A GPSMessageObject containing the received message
    @abc.abstractmethod
    def addGPSMessageToUI(self, gps_msg):
        raise NotImplementedError
    
    ##@brief add a new GPS contact widget to kivy that contains information in gps_msg
    ##@param gps_msg A GPSMessageObject
    def addNewGPSContactToUI(self, gps_msg):
        raise NotImplementedError
    
    ##@brief modify an existing GPS contact widget with new information contained in gps_msg
    ##@param gps_msg A GPSMessageObject
    ##@throws throws a InputError when gps_msg does not match an existing GPS contact widget
    def updateGPSContact(self, gps_msg):
        raise NotImplementedError
        
    ##@brief update the UI to show that a GPS signal lock has been achieved
    def notifyGPSLockAchieved(self):
        raise NotImplementedError
    
    
    ##@brief start the UI
    @abc.abstractmethod
    def run(self):
        raise NotImplementedError
