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
    def update_tx_success_cnt(self,val):
        raise NotImplementedError
        
    @abc.abstractmethod
    def update_tx_failure_cnt(self,val):
        raise NotImplementedError
        
    @abc.abstractmethod
    def update_rx_success_cnt(self,val):
        raise NotImplementedError
        
    @abc.abstractmethod
    def update_rx_failure_cnt(self,val):
        raise NotImplementedError
    
    @abc.abstractmethod
    def clearReceivedMessages(self):
        raise NotImplementedError

    @abc.abstractmethod
    def isTestTxChecked(self):
        raise NotImplementedError
    
    @abc.abstractmethod
    def isAckChecked(self):
        raise NotImplementedError
    

    ##@brief start the UI
    @abc.abstractmethod
    def run(self):
        raise NotImplementedError
