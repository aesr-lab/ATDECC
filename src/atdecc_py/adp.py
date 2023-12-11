import time
import random
import logging
import copy
from threading import Thread, Event
from queue import Queue, Empty

from pdu import *
from pdu_print import *
from aem import *
from util import *

class EntityInfo:
    """
    IEEE 1722.1-2021, section 6.2.2
    ATDECC Discovery Protocol PDU
    
    All ids are stored in uint64 format (not EUIxx) 
    """

    def __init__(self, 
                 valid_time=62,
                 entity_id=0,
                 entity_model_id=0,
                 entity_capabilities=0,
                 talker_stream_sources=0,
                 talker_capabilities=0,
                 listener_stream_sinks=0,
                 listener_capabilities=0,
                 controller_capabilities=0,
                 gptp_grandmaster_id=0,
                 gptp_domain_number=0,
                 current_configuration_index=0,
                 identify_control_index=0,
                 interface_index=0,
                 association_id=0,
                 ):
        self.valid_time = valid_time # in seconds
        self.entity_id = entity_id #  Section 6.2.2.7., "In the case of an EndStation containing multiple ATDECC Entities, each ATDECC Entity has a unique Entity ID."
        self.entity_model_id = entity_model_id # Section 6.2.2.8., "If a firmware revision changes the structure of an ATDECC Entity data model then it shall use a new unique entity_model_id."
        # TODO we should probably test all the capabilities for inclusion in the respective enums
        self.entity_capabilities = entity_capabilities
        self.talker_stream_sources = talker_stream_sources # Section 6.2.2.10., "the maximum number of Streams an ATDECC Talker is capable of sourcing simultaneously." NOT the current number of stream sources -> see Entity description
        self.talker_capabilities = talker_capabilities
        self.listener_stream_sinks = listener_stream_sinks # Section 6.2.2.13., "the maximum number of Streams an ATDECC Listener is capable of sinking simultaneously." NOT the current number of stream sinks -> see Entity description
        self.listener_capabilities = listener_capabilities
        self.controller_capabilities = controller_capabilities
        self.available_index = 0
        self.gptp_grandmaster_id = gptp_grandmaster_id
        self.gptp_domain_number = gptp_domain_number
        self.current_configuration_index = current_configuration_index
        self.identify_control_index = identify_control_index
        self.interface_index = interface_index
        self.association_id = association_id # Section 6.2.2.21., "used to associate multiple ATDECC entities into a logical collection. This allows each loudspeaker of a multi-channel rig to be a separate ATDECC entity but to be associated by the ATDECC Controler into a single logical ATDECC entity"
        
    def get_adpdu(self):
        return at.struct_jdksavdecc_adpdu(
            header = at.struct_jdksavdecc_adpdu_common_control_header(
                valid_time=max(1,min(int(self.valid_time/2.+0.5),31)),
                entity_id=uint64_to_eui64(self.entity_id),
            ),
            entity_model_id = uint64_to_eui64(self.entity_model_id),
            entity_capabilities=self.entity_capabilities,
            talker_stream_sources=self.talker_stream_sources,
            talker_capabilities=self.talker_capabilities,
            listener_stream_sinks=self.listener_stream_sinks,
            listener_capabilities=self.listener_capabilities,
            controller_capabilities=self.controller_capabilities,
            available_index=self.available_index,
            gptp_grandmaster_id=uint64_to_eui64(self.gptp_grandmaster_id),
            gptp_domain_number=self.gptp_domain_number,
            current_configuration_index=self.current_configuration_index,
            identify_control_index=self.identify_control_index,
            interface_index=self.interface_index,
            association_id=uint64_to_eui64(self.association_id),
        )


class GlobalStateMachine:
    """
    IEEE 1722.1-2021, section 6.2.3
    """
    @property
    def currentTime(self):
        """
        Get seconds in epoch
        """
        return time.time()


class AdvertisingEntityStateMachine(
    GlobalStateMachine,
    Thread
    ):
    """
    IEEE 1722.1-2021, section 6.2.4

    for each ATDECC Entity being published on the End Station
    """

    def __init__(self, entity_info, interface_state_machines):
        super(AdvertisingEntityStateMachine, self).__init__()
        self.entity_info = entity_info
        self.reannouncementTimerTimeout = 0
        self.needsAdvertise = False
        self.doTerminate = False
        self.event = Event()
        self.random = random.Random()
        self.random.seed(self.entity_info.entity_id+int(self.currentTime*10**6))
        self.interface_state_machines = interface_state_machines

    def performAdvertise(self):
        self.needsAdvertise = True
        self.event.set()

    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()

    def sendAvailable(self):
        """
        Sets all of the doAdvertise booleans on all of the Advertising Interface 
        state machines to signal them to transmit an advertise message.
        """
        for ism in self.interface_state_machines:
            ism.performAdvertise()

    def randomDeviceDelay(self):
        """
        returns the number of milliseconds that the device should wait between 
        the firing of the re­announce timer or being requested to send an 
        ENTITY_ADVERTISE message and sending the message. 
        The randomDeviceDelay function generates a random delay with a 
        uniform distribution across the range of zero (0) to 1/5 of the 
        valid time of the ATDECC Entity in milliseconds.
        """
        return self.random.uniform(0, self.entity_info.valid_time/5.) * 1000.

    def run(self):
        logging.debug("AdvertisingEntityStateMachine: Starting thread")

        # INITIALIZE
        self.entity_info.available_index = 0

        while True:
            # DELAY
            self.event.wait(self.randomDeviceDelay() / 1000.)
            if self.doTerminate:
                break
            self.event.clear()

            # ADVERTISE
            self.sendAvailable()

            self.needsAdvertise = False

            # WAITING
            if not self.needsAdvertise:
              self.event.wait(max(1, self.entity_info.valid_time/2))
            if self.doTerminate:
                break
            self.event.clear()

        logging.debug("AdvertisingEntityStateMachine: Ending thread")


class DiscoveryStateMachine(
    GlobalStateMachine, 
    Thread
    ):
    """
    IEEE 1722.1-2021, section 6.2.6
    
    for each ATDECC Entity implementing an ATDECC Controller or 
    requiring Entity discovery
    """

    def __init__(self, interfaces, discoverID=0):
        super(DiscoveryStateMachine, self).__init__()

        self.discoverID = discoverID # 0 discovers everything
        self.rcvdEntityInfo = None
        self.rcvdAvailable = False
        self.rcvdDeparting = False

        self.doDiscover = False
        self.doTerminate = False
        self.event = Event()

        self.entities = {}
        self.interfaces = []

    def performTerminate(self):
        self.doTerminate = True
        self.event.set()
        
    def performDiscover(self):
        self.doDiscover = True
        self.event.set()
        
    def txDiscover(self, entityID):
        """
        The txDiscover function transmits an ENTITY_DISCOVER message.
        If the ATDECC Entity has more than one enabled network port, 
        then the same ADPDU is sent out each port.
        """
        raise NotImplementedError()
        
    def haveEntity(self, entityID):
        return entityID in self.entities

    def addEntity(self, entityInfo, ct=GlobalStateMachine().currentTime):
        """
        The addEntity function adds a new Entity record to the entities variable with the contents of the entityInfo structure parameter.

        """
        self.updateEntity(entityInfo, ct)

    def updateEntity(self, entityInfo, ct=GlobalStateMachine().currentTime):
        if entityInfo.entity_id:
            self.entities[entityInfo.entity_id] = (entityInfo, ct+entityInfo.valid_time)
        else:
            logging.warning("entityID == 0")

    def removeEntity(self, eui64):
        """
        The remove Entity function removes an ATDECC Entity record from the entities variable for an ATDECC Entity whose entity_id matches the eui64 parameter.
        """
        try:
            del self.entities[eui64_to_uint64(eui64)]
        except KeyError:
            logging.warning("entityID not found in database")
            
    def run(self):
        while True:
            # WAITING
            self.rcvdAvailable = False
            self.rcvdDeparting = False
            self.doDiscover = False

            self.event.wait(1)
            if self.doTerminate:
                break
            self.event.clear()

            # DISCOVER
            if self.doDiscover:
                self.txDiscover(self.discoverID)

            ct = self.currentTime

            # AVAILABLE
            if self.rcvdAvailable:
                if self.haveEntity(self.rcvdEntityInfo.entity_id):
                    self.updateEntity(self.rcvdEntityInfo, ct)
                else:
                    self.addEntity(self.rcvdEntityInfo, ct)

            # DEPARTING
            if self.rcvdDeparting:
                self.removeEntity(uint64_to_eui64(self.rcvdEntityInfo.entity_id))

            # TIMEOUT
            for key in self.entities:
                entity_info, timeout = self.entities[key]
                if ct >= timeout:
                    self.removeEntity(uint64_to_eui64(entity_info.entity_id))


# combined:
# AdvertisingInterfaceStateMachine
# DiscoveryInterfaceStateMachine
class InterfaceStateMachine(Thread):
    """
    IEEE 1722.1-2021, section 6.2.5
    for each AVB interface of the ATDECC Entity being published in the End Station

    IEEE 1722.1-2021, section 6.2.7    
    """
    
    def __init__(self, entity_info, interfaces):
        super(InterfaceStateMachine, self).__init__()
        
        self.event = Event()
        self.doTerminate = False

        # AdvertisingInterfaceStateMachine
        self.doAdvertise = False
        self.interfaces = interfaces
        self.entity_info = entity_info
        
        # DiscoveryInterfaceStateMachine
        self.rcvdDiscover = Queue()
        self.currentGrandmasterID = None
        self.advertisedGrandmasterID = None
        self.linkIsUp = True
        self.lastLinkIsUp = False
        self.currentConfigurationIndex = 0
        self.advertisedConfigurationIndex = None
        
        
    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()
        
    def performAdvertise(self):
        self.doAdvertise = True
        self.event.set()
        
    def txEntityAvailable(self):
        """
        The txEntityAvailable function transmits an ENTITY_AVAILABLE message
        """
        for intf in self.interfaces:
            intf.send_adp(at.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_AVAILABLE, self.entity_info)

        self.entity_info.available_index += 1        

    def txEntityDeparting(self):
        """
        The txEntityAvailable function transmits an ENTITY_DEPARTING message
        """
        for intf in self.interfaces:
            intf.send_adp(at.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity_info)

        self.entity_info.available_index = 0


    def adp_cb(self, adpdu):
        """
        The entityID variable is an unsigned 64bit value containing the entity_id from the received ENTITY_DISCOVER ADPDU. This is set at the same time and from the same ADPDU as rcvdDiscover. 
        """
#        logging.info("ADP: %s", adpdu_str(adpdu))

        if adpdu.header.message_type == at.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER:
            self.rcvdDiscover.put(copy.deepcopy(adpdu.header.entity_id))

    def run(self):
        logging.debug("InterfaceStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_adp_cb(self.adp_cb)

        while True:
            if self.rcvdDiscover.empty():
                self.event.wait(1)
                # signalled
                self.event.clear()
                
            if self.doTerminate:
                break
            
            # AdvertisingInterfaceStateMachine
            if self.doAdvertise:
                self.txEntityAvailable()
                self.doAdvertise = False
                
            # DiscoveryInterfaceStateMachine
            try:
                disc = eui64_to_uint64(self.rcvdDiscover.get_nowait())
            except Empty:
                disc = None
                
            if disc is not None:
                # RECEIVED DISCOVER
                if disc == 0 or disc == self.entity_info.entity_id:
                    # DISCOVER
                    logging.debug("Respond to Discover")
                    self.performAdvertise()
            
            if self.currentGrandmasterID != self.advertisedGrandmasterID:
                # UPDATE GM
                logging.debug("Update GrandmasterID")
                self.advertisedGrandmasterID = self.currentGrandmasterID
                self.performAdvertise()
                
            if self.lastLinkIsUp != self.linkIsUp:
                # LINK STATE CHANGE
                logging.debug("Update Link state")
                self.lastLinkIsUp = self.linkIsUp 
                if self.linkIsUp:
                    self.performAdvertise()
                    
            if self.currentConfigurationIndex != self.advertisedConfigurationIndex:
                # UPDATE CONFIGURATION
                logging.debug("Update Configuration")
                self.advertisedConfigurationIndex = self.currentConfigurationIndex 
                self.performAdvertise()

        # thread ending
        self.txEntityDeparting()

        for intf in self.interfaces:
            intf.unregister_adp_cb(self.adp_cb)

        logging.debug("InterfaceStateMachine: Ending thread")
