#!/usr/bin/env python3

import ctypes
import struct
import avdecc_api as av
from avdecc_api import AVDECC_create, AVDECC_destroy, AVDECC_send_frame, AVDECC_send_adp, AVDECC_set_adpdu, AVDECC_send_acmp, AVDECC_send_aecp
import time
import logging
from threading import Thread, Event
from queue import Queue, Empty
import copy
import random
import traceback
import pdb


from pdu import *
from pdu_print import *
from aem import *


class EntityInfo:
    """
    IEEE 1722.1-2021, section 6.2.7
    
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
        self.entity_id = entity_id
        self.entity_model_id = entity_model_id # Section 6.2.2.8.
        self.entity_capabilities = entity_capabilities
        self.talker_stream_sources = talker_stream_sources
        self.talker_capabilities = talker_capabilities
        self.listener_stream_sinks = listener_stream_sinks
        self.listener_capabilities = listener_capabilities
        self.controller_capabilities = controller_capabilities
        self.available_index = 0
        self.gptp_grandmaster_id = gptp_grandmaster_id
        self.gptp_domain_number = gptp_domain_number
        self.current_configuration_index = current_configuration_index
        self.identify_control_index = identify_control_index
        self.interface_index = interface_index
        self.association_id = association_id
        
    def get_adpdu(self):
        return av.struct_jdksavdecc_adpdu(
            header = av.struct_jdksavdecc_adpdu_common_control_header(
                valid_time=max(0,min(int(self.valid_time/2.+0.5),31)),
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


class jdksInterface:
    handles = {}
    
    def __init__(self, ifname):
        self.ifname = ifname
        
        self.adp_cbs = []
        self.acmp_cbs = []
        self.aecp_aem_cbs = []

        self.handle = ctypes.c_void_p()
        intf = ctypes.c_char_p(self.ifname.encode())
        res = AVDECC_create(ctypes.byref(self.handle), 
                            intf, 
                            self._adp_cb, 
                            self._acmp_cb, 
                            self._aecp_aem_cb
                            )
        assert res == 0
        logging.debug("AVDECC_create done")
        jdksInterface.handles[self.handle.value] = self  # register instance
    
    def __del__(self):
        res = AVDECC_destroy(self.handle)
        logging.debug("AVDECC_destroy done")
        assert res == 0
        del self.handles[self.handle.value]  # unregister instance
        self.handle.value = None
    
    def send_adp(self, msg, entity):
        pdu = entity.get_adpdu()
        if True:
            frame = adp_form_msg(pdu, msg, uint64_to_eui64(entity.entity_id))
            res = AVDECC_send_frame(self.handle, frame)
            assert res == 0
        else:
            res = AVDECC_set_adpdu(self.handle, pdu)
            assert res == 0
            res = AVDECC_send_adp(self.handle, msg, av.uint64_t(entity.entity_id))
            assert res == 0
#        logging.debug("AVDECC_send_adp: %s", adpdu_str(pdu))

    def send_aecp(self, pdu, payload):
#        logging.debug(f"AVDECC_send_aecp: %s", aecpdu_aem_str(pdu))
        frame = aecp_form_msg(pdu, command_payload=payload)
#        if frame.payload:
#            logging.debug("frame payload: %s", bytes(frame.payload).hex())
        res = AVDECC_send_frame(self.handle, frame)

    def register_adp_cb(self, cb):
        self.adp_cbs.append(cb)

    def unregister_adp_cb(self, cb):
        self.adp_cbs.remove(cb)

    def register_acmp_cb(self, cb):
        self.acmp_cbs.append(cb)

    def unregister_acmp_cb(self, cb):
        self.acmp_cbs.remove(cb)

    def register_aecp_aem_cb(self, cb):
        self.aecp_aem_cbs.append(cb)

    def unregister_aecp_aem_cb(self, cb):
        self.aecp_aem_cbs.remove(cb)

    @av.AVDECC_ADP_CALLBACK
    def _adp_cb(handle, frame_ptr, adpdu_ptr):
        this = jdksInterface.handles[handle]
        du = adpdu_ptr.contents
        if len(this.adp_cbs) == 0:
            logging.debug("Unhandled ADP: %s - %s", adpdu_str(du), this.adp_cbs)
        else:
            for cb in this.adp_cbs:
                cb(du)

    @av.AVDECC_ACMP_CALLBACK
    def _acmp_cb(handle, frame_ptr, acmpdu_ptr):
        this = jdksInterface.handles[handle]
        du = acmpdu_ptr.contents
        if len(this.acmp_cbs) == 0:
            logging.debug("Unhandled ACMP: %s", acmpdu_str(du))
        else:
            for cb in this.acmp_cbs:
                cb(du)

    @av.AVDECC_AECP_AEM_CALLBACK
    def _aecp_aem_cb(handle, frame_ptr, aecpdu_aem_ptr):
        this = jdksInterface.handles[handle]
        du = aecpdu_aem_ptr.contents
        frame = frame_ptr.contents
        if len(this.aecp_aem_cbs) == 0:
            logging.debug("Unhandled AECP_AEM: %s", aecpdu_aem_str(du))
        else:
            cmd_payload = bytes(frame.payload)[24:]
            for cb in this.aecp_aem_cbs:
                cb(du, cmd_payload)


class Interface(jdksInterface):
    def __init__(self, ifname):
        super(Interface, self).__init__(ifname)
        self.mac = intf_to_mac(self.ifname) # MAC as string
        logging.debug(f"MAC: {self.mac}")


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
        return self.random.uniform(0, self.entity_info.valid_time/5.)

    def run(self):
        logging.debug("AdvertisingEntityStateMachine: Starting thread")

        self.entity_info.available_index = 0

        while True:
            self.event.wait(self.randomDeviceDelay())
            if self.doTerminate:
                break
            self.event.clear()

            self.sendAvailable()

            self.needsAdvertise = False

            self.event.wait(max(1, self.entity_info.valid_time/2))
            if self.doTerminate:
                break
            self.event.clear()

        logging.debug("AdvertisingEntityStateMachine: Ending thread")


if 0:
    class AdvertisingInterfaceStateMachine(Thread):
        """
        IEEE 1722.1-2021, section 6.2.5
    
        for each AVB interface of the ATDECC Entity being published in the End Station
        """
    
        def __init__(self, entity_info, interfaces):
            super(AdvertisingInterfaceStateMachine, self).__init__()
            self.entity_info = entity_info
            self.doTerminate = False
            self.doAdvertise = False
            self.interfaces = interfaces
            self.event = Event()
        
        def performTerminate(self):
            self.doTerminate = True
            self.event.set()
        
        def performAdvertise(self):
            self.doAdvertise = True
            self.event.set()
        
        def txEntityAvailable(self):
            """
            The txEntityAvailable function transmits an ENTITY_AVAILABLE message
            """
            for intf in self.interfaces:
                intf.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_AVAILABLE, self.entity_info)

        def txEntityDeparting(self):
            """
            The txEntityAvailable function transmits an ENTITY_DEPARTING message
            """
            for intf in self.interfaces:
                intf.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity_info)

        def run(self):
            logging.debug("AdvertisingInterfaceStateMachine: Starting thread")

            while True:
                self.event.wait(1)
                # signalled
                self.event.clear()
            
                if self.doTerminate:
                    break
                elif self.doAdvertise:
                    self.txEntityAvailable()
                    self.doAdvertise = False

            self.txEntityDeparting()

            logging.debug("AdvertisingInterfaceStateMachine: Ending thread")


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

    def updateEntity(self, entityInfo, ct=GlobalStateMachine.currentTime):
        if entityInfo.entityID:
            self.entities[entityInfo.entityID] = (entityInfo, ct+entityInfo.valid_time)
        else:
            logging.warning("entityID == 0")

    def removeEntity(self, entityID):
        try:
            del self.entities[entityID]
        except KeyError:
            logging.warning("entityID not found in database")
            
    def run(self):
        while True:
            self.rcvdAvailable = False
            self.rcvdDeparting = False
            self.doDiscover = False

            self.event.wait(1)
            if self.doterminate:
                break
            self.event.clear()

            if self.doDiscover:
                txDiscover(self.discoverID)

            ct = self.currentTime

            if self.rcvdAvailable:
                thisEntity = self.updateEntity(self.rcvdEntityInfo, ct)

            if self.rcvdDeparting:
                self.removeEntity(self.rcvdEntityInfo.entity_id)

            for e in self.entities:
                if ct >= e.timeout:
                    self.removeEntity(e.entity_id)


class DiscoveryInterfaceStateMachine(
    GlobalStateMachine, 
    Thread
    ):
    """
    IEEE 1722.1-2021, section 6.2.7
    """

    def __init__(self):
        self.doTerminate = False
        self.needsAdvertise = False
        self.currentGrandmasterID = None
        self.advertisedGrandmasterID = None
        self.rcvdDiscover = None
        self.entityID = 0
        self.linkIsUp = False
        self.lastLinkIsUp = False
        self.currentConfigurationIndex = None
        self.advertisedConfigurationIndex = None
        self.event = Event()
        
    def performTerminate(self):
        self.doTerminate = True
        self.event.set()
        
    def adp_cb(self, adpdu):
        logging.info("ADP: %s", adpdu_str(adpdu))
        
    def run(self):
        self.lastLinkIsUp = False
        self.advertisedGrandmasterID = self.currentGrandmasterID
        
        while True:
            self.event.wait()
            if self.doTerminate:
                break

            self.event.clear()
            
            if self.rcvdDiscover:
                # RECEIVED DISCOVER
                self.rcvdDiscover = False
                
                if entity_id == 0 or entity_id == entityInfo.entity_id:
                    # DISCOVER
                    self.needsAdvertise = True
            
            if self.currentGrandmasterID != self.advertisedGrandmasterID:
                # UPDATE GM
                self.advertisedGrandmasterID = self.currentGrandmasterID
                self.needsAdvertise = True
                
            if self.lastLinkIsUp != self.linkIsUp:
                # LINK STATE CHANGE
                self.lastLinkIsUp = self.linkIsUp 
                if self.linkIsUp:
                    self.needsAdvertise = True
                    
            if self.currentConfigurationIndex != self.advertisedConfigurationIndex:
                # UPDATE CONFIGURATION
                self.advertisedConfigurationIndex = self.currentConfigurationIndex 
                self.needsAdvertise = True


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
            intf.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_AVAILABLE, self.entity_info)

        self.entity_info.available_index += 1        

    def txEntityDeparting(self):
        """
        The txEntityAvailable function transmits an ENTITY_DEPARTING message
        """
        for intf in self.interfaces:
            intf.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity_info)

        self.entity_info.available_index = 0


    def adp_cb(self, adpdu):
#        logging.info("ADP: %s", adpdu_str(adpdu))

        if adpdu.header.message_type == av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER:
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
                disc = self.rcvdDiscover.get_nowait()
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


class ACMPListenerStateMachine(
    GlobalStateMachine, 
    Thread
    ):
    """
    IEEE 1722.1-2021, section 8.2.4
    """
    
    def __init__(self, entity_info, interfaces):
        super(ACMPListenerStateMachine, self).__init__()
        self.event = Event()
        self.queue = Queue()
        self.doTerminate = False
        self.interfaces = interfaces
        
        self.my_id = entity_info.entity_id
        self.inflight = []
        self.listenerStreamInfos = {}
        self.rcvdConnectRXCmd = False
        self.rcvdDisconnectRXCmd = False
        self.rcvdConnectTXResp = False
        self.rcvdDisconnectTXResp = False
        self.rcvdGetRXState = False

    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()

    def acmp_cb(self, acmpdu: av.struct_jdksavdecc_acmpdu):
        if eui64_to_uint64(acmpdu.listener_entity_id) == self.my_id:
            logging.info("ACMP: %s", acmpdu_str(acmpdu))
            self.queue.put(copy.deepcopy(acmpdu)) # copy structure (will probably be overwritten)
            self.event.set()

    def validListenerUnique(self, ListenerUniqueId):
        """
        The validListenerUnique function returns a Boolean indicating if the 
        ATDECC ListenerUniqueId passed in is valid for the ATDECC Entity.
        """
        return ListenerUniqueId == self.my_id

    def listenerIsConnected(self, command):
        """
        The listenerIsConnected function returns a Boolean indicating if the 
        ATDECC Listener is already connected to or attempting to connect to a 
        stream source other than the one specified by the talker_entity_id and talker_unique_id in the command.
        
        This function returns TRUE if either connected is TRUE or pending_connections is TRUE 
        and talker_entity_id and talker_unique_id in the command does not matches 
        talker_entity_id and talker_unique_id in the listenerStreamInfos entry otherwise it returns FALSE.
        
        NOTE: This function returns FALSE when being asked if it is connected to the 
        same stream so that after an unclean disconnection (the ATDECC Talker disappearing 
        and then reappearing without an intermediate DISCONNECT_RX_COMMAND being sent) 
        the next connection attempt by the ATDECC Controller to restore the connection will succeed.
        """
        raise NotimplementedError()

    def listenerIsConnectedTo(self, command):
        """
        The listenerIsConnectedTo function returns a Boolean indicating 
        if the ATDECC Listener is already connected to the stream source 
        specified by the talker_entity_id and talker_unique_id in the command.
        
        This function returns TRUE if connected is TRUE and talker_entity_id 
        and talker_unique_id in the command matches talker_entity_id and talker_unique_id 
        in the listenerStreamInfos entry otherwise it returns FALSE.
        """
        raise NotimplementedError()

    def txCommand(self, messageType, command, retry):
        """
        The txCommand function transmits a command of type messageType. 
        It sets the ACMPDU fields to the values from the command 
        ACMPCommandResponse parameter and the message_type field to the value of messageType.
        
        If this function successfully sends the message and it is not a retry 
        then it adds an InflightCommand entry to the inflight variable 
        with the command field set to the passed in command, 
        the timeout field set to the value of currentTime + the appropriate timeout for the messageType (see Table 8­1), 
        the retried field set to FALSE and the sequence_id field set to the sequence_id used for the transmitted message. 
        This starts the timeout timer for this command.
        
        If this function successfully sends the message and it is a retry 
        then it updates the InflightCommand entry of the inflight variable 
        corresponding with this command by setting the timeout field to the value of currentTime + the appropriate timeout 
        for the messageType (see Table 8­1) and the retried field set to TRUE. 
        This starts the timeout timer for this command.
        
        If this function fails to send the message (e.g., there are no available InFlightCommand entries to use) 
        then it calls the txResponse function with the appropriate response code for the messageType (messageType + 1), 
        the passed in command and the status code of COULD_NOT_SEND_MESSAGE. 
        If this was a retry then the InFlightCommand entry corresponding to the command is removed from the inflight variable.
        
        This function returns TRUE if it sent a command or FALSE otherwise.
        """
        raise NotimplementedError()

    def txResponse(self, messageType, response, error):
        """
        The txResponse function transmits a response of type messageType. 
        It sets the ACMPDU fields to the values from the response parameter, 
        the message_type field to the value of messageType and the status field to the value of the error parameter.
        """
        raise NotimplementedError()

    def connectListener(self, response):
        """
        The connectListener function uses the passed in response structure to connect a stream to the ATDECC Listener.
        
        This function sets the fields of the ATDECC ListenerStreamInfos entry for the listener_unique_id 
        to the values of the equivalent fields in the response structure, 
        set the connected field to TRUE and initiates an SRP Listener registration.
        
        The connectListener function returns the response structure, with any updated flags. 
        The connectListener function also returns a status code as defined in Table 8­3 
        indicating either SUCCESS or the reason for a failure.
        """
        raise NotimplementedError()

    def disconnectListener(self, command):
        """
        The disconnectListener function uses the passed in command structure 
        to disconnect the stream from an ATDECC Listener.
        
        This function initiates an SRP Talker de­registration and sets all fields of the 
        ATDECC ListenerStreamInfos entry for the listener_unique_id to zero (0) or FALSE.
        
        The disconnectListener function returns the command structure, with any updated flags. 
        The discon­ nectListener function also returns a status code as defined in Table 8­3 
        indicating either SUCCESS or the reason for a failure.
        """
        raise NotimplementedError()

    def cancelTimeout(self, commandResponse):
        """
        The cancelTimeout function stops the timeout timer of the inflight entry 
        associated with the comman­ dResponse parameter. 
        The commandResponse may be a copy of the command entry within the inflight entry 
        or may be the response received for that command.
        """
        raise NotimplementedError()

    def removeInflight(self, commandResponse):
        """
        The removeInflight function removes an entry from the inflight variable 
        associated with the comman­ dResponse parameter. 
        The commandResponse may be a copy of the command entry within the inflight entry 
        or may be the response received for that command.
        """
        raise NotimplementedError()

    def getState(self, command):
        """
        The getState function returns a response structure of type ACMPCommandResponse 
        filled with the contents of the command parameter, with the stream_id, 
        stream_dest_mac, stream_vlan_id, connection_count, flags, talker_entity_id 
        and talker_unique_id fields set to the values for the ATDECC ListenerStreamInfos entry 
        associated with the stream identified by the command structure. 
        The getState function also returns a status code as defined in Table 8­3 
        indicating either SUCCESS or the reason for a failure.
        """
        raise NotimplementedError()

    def listenerIsAcquiredOrLockedByOther(self, commandResponse):
        """
        The listenerIsAcquiredOrLockedByOther function returns a Boolean 
        indicating if the stream has been acquired or locked for exclusive access by another ATDECC Controller.

        If the ATDECC Listener does not implement the ATDECC Entity Model 
        then this function result is based on similar functionality from the enumeration 
        and control protocol being used. If there is no enumeration and control protocol then this function returns FALSE.

        If the ATDECC Listener does implement the ATDECC Entity Model then this function returns TRUE 
        if the STREAM_INPUT representing this stream has been acquired by an ATDECC Controller 
        and the controller_entity_id field of the commandResponse does not match 
        the acquiring ATDECC Controller’s Entity ID or if the STREAM_INPUT representing this stream 
        has been locked by an ATDECC Controller and the controller_entity_id field of the commandResponse 
        does not match the acquiring ATDECC Controller’s Entity ID. Otherwise it returns FALSE.
        """
        raise NotimplementedError()

    def run(self):
        logging.debug("ACMPListenerStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_acmp_cb(self.acmp_cb)

        while True:
            self.rcvdConnectRXCmd = False
            self.rcvdDisconnectRXCmd = False
            self.rcvdConnectTXResp = False
            self.rcvdDisconnectTXResp = False
            self.rcvdGetRXState = False
            
            if self.queue.empty():
                self.event.wait(1)
                # signalled
                self.event.clear()
                
            if self.doTerminate:
                break
                
            try:
                cmd = self.queue.get_nowait()
                self.inflight.append(cmd)
            except Empty:
                pass
            
            try:
                # check timeouts
                ct = self.currentTime
                retried = []

                # self.inflight: list struct_jdksavdecc_acmpdu

                if len(self.inflight):
                    import pdb
                    pdb.set_trace()
                
                    while len(self.inflight) and ct >= self.inflight[0].timeout:
                        infl = self.inflight.pop(0)
                        if infl.command.message_type == av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND:
                            # CONNECT TX TIMEOUT
                            if infl.retried:
                                response = infl.command
                                response.sequence_id = infl.original_sequence_id
                                listenerInfo = self.listenerStreamInfos[rcvdCmdResp.listener_unique_id]
                                listenerInfo.pending_connection = False
                                self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, response, av.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)
                            else:
                                # Retry
                                self.txCommand(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, infl.command, True)
                                infl.retried = True
                                retried.append(infl)
                        
                        elif infl.command.message_type == av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND:
                            # DISCONNECT TX TIMEOUT
                            if infl.retried:
                                response = infl.command
                                response.sequence_id = infl.original_sequence_id
                                self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, av.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)
                            else:
                                self.txCommand(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND, infl.command, True)
                                infl.retried = True
                                retried.append(infl)
                        
                # reinsert retries into inflights
                for infl in retried[::-1]:
                    self.inflight.insert(0, infl)
            
                if self.rcvdConnectRXCmd:
                    # CONNECT RX COMMAND
                    logging.debug("Received Connect RX command")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        if self.listenerIsAcquiredOrLockedByOther(self.rcvdCmdResp):
                            self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, self.rcvdCmdResp, av.JDKSAVDECC_ACMP_STATUS_CONTROLLER_NOT_AUTHORIZED)
                        elif self.listenerIsConnected(self.rcvdCmdResp):
                            self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, self.rcvdCmdResp, av.JDKSAVDECC_ACMP_STATUS_LISTENER_EXCLUSIVE)
                        else:
                            if self.txCommand(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, self.rcvdCmdResp, False):
                                listenerInfo = self.listenerStreamInfos[self.rcvdCmdResp.listener_unique_id]
                                listenerInfo.talker_entity_id = self.rcvdCmdResp.talker_entity_id
                                listenerInfo.talker_unique_id = self.rcvdCmdResp.talker_unique_id
                                listenerInfo.pending_connection = True
                    else:
                        self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, self.rcvdCmdResp, av.JDKSAVDECC_ACMP_STATUS_LISTENER_UNKNOWN_ID)

                    self.rcvdConnectRXCmd = False

                if self.rcvdConnectTXResp:
                    # CONNECT TX RESPONSE
                    logging.debug("Received Connect TX response")

                    if  self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        if self.rcvdCmdResp.status == av.JDKSAVDECC_ACMP_STATUS_SUCCESS:
                            response, status = self.connectListener(self.rcvdCmdResp)
                        else:
                            response, status = (self.rcvdCmdResp, self.rcvdCmdResp.status)
                        
                        listenerInfo = self.listenerStreamInfos[self.rcvdCmdResp.listener_unique_id]
                        listenerInfo.pending_connection = False
                    
                        import pdb
                        pdb.set_trace()
                        response.sequence_id = inflight[x].original_sequence_id # ????
                        self.cancelTimeout(self.rcvdCmdResp)
                        removeInflight(rcvdCmdResp) # ????
                        self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, response, status)

                    self.rcvdConnectTXResp = False

                if self.rcvdGetRXState:
                    # GET STATE
                    logging.debug("Received Get State")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        response, error = self.getState(self.rcvdCmdResp)
                    else:
                        response, error = (self.rcvdCmdResp, av.JDKSAVDECC_ACMP_STATUS_LISTENER_UNKNOWN_ID)
                    
                    self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_RESPONSE, response, error)

                    self.rcvdGetRXState = False

                if self.rcvdDisconnectRXCmd:
                    # DISCONNECT RX COMMAND
                    logging.debug("Received Disconnect RX command")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        if self.listenerIsConnectedTo(self.rcvdCmdResp):
                            response, status = self.disconnectListener(self.rcvdCmdResp)
                            if status == av.JDKSAVDECC_ACMP_STATUS_SUCCESS:
                                self.txCommand(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND, self.rcvdCmdResp, False)
                            else:
                                self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, status)
                        else:
                            self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, self.rcvdCmdResp, av.JDKSAVDECC_ACMP_STATUS_NOT_CONNECTED)
                    else:
                        self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, self.rcvdCmdResp, av.JDKSAVDECC_ACMP_STATUS_LISTENER_UNKNOWN_ID)

                    self.rcvdDisconnectRXCmd = False

                if self.rcvdDisconnectTXResp:
                    # CONNECT TX RESPONSE
                    logging.debug("Received Disconnect TX response")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        response, status = (self.rcvdCmdResp, self.rcvdCmdResp.status)

                        import pdb
                        pdb.set_trace()
                        response.sequence_id = inflight[x].original_sequence_id # ???
                        self.cancelTimeout(self.rcvdCmdResp)
                        removeInflight(self.rcvdCmdResp)  # ???
                        self.txResponse(av.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, status)

                    self.rcvdDisconnectTXResp = False
            except Exception as e:
                traceback.print_exc()
#                logging.error("Exception: %s", e)

        for intf in self.interfaces:
            intf.unregister_acmp_cb(self.acmp_cb)

        logging.debug("ACMPListenerStateMachine: Ending thread")


# An ATDECC Talker or Listener shall implement and respond to the 
# ACQUIRE_ENTITY, LOCK_ENTITY, and ENTITY_AVAILABLE commands. 
# All other commands are optional for an ATDECC Talker or Listener.

class EntityModelEntityStateMachine(Thread):
    """
    IEEE 1722.1-2021, section 9.3.5
    """
    
    def __init__(self, entity_info, interfaces):
        super(EntityModelEntityStateMachine, self).__init__()
        self.event = Event()
        self.doTerminate = False
        self.interfaces = interfaces
        
        self.rcvdCommand = Queue()
        self.entity_info = entity_info
        self.unsolicited = None
        self.unsolicitedSequenceID = 0
        self.unsolicited_list = set()
        
        self.owner_entity_id = 0 # uint64
        
    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()
        
    def aecp_aem_cb(self, aecp_aemdu: av.struct_jdksavdecc_aecpdu_common, payload=None):
        if eui64_to_uint64(aecp_aemdu.aecpdu_header.header.target_entity_id) == self.entity_info.entity_id:
            logging.info("AECP AEM: %s", aecpdu_aem_str(aecp_aemdu))

#            print(f"AECP %x: %s"%(aecp_aemdu.aecpdu_header.header.message_type, hexdump(payload[:16])))

            if aecp_aemdu.aecpdu_header.header.message_type == av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND:
                self.rcvdCommand.put((copy.deepcopy(aecp_aemdu), payload)) # copy structure, will probably be overwritten
                self.event.set()

    def acquireEntity(self, command: av.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The acquireEntity function is used to handle the receipt, processing and respond to an ACQUIRE_ENTITY AEM Command (7.4.1).
        
        The acquireEntity function handles checking the current status of the acquisition, issuing any required 
        CONTROLLER_AVAILABLE AEM Command (7.4.4) and dealing with the response and sending any required IN_PROGRESS responses 
        for the passed in command.
        acquireEntity returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command ACQUIRE_ENTITY
 
        logging.debug("ACQUIRE_ENTITY")
        
        aem_acquire_flags, owner_entity_id, descriptor_type, descriptor_index = struct.unpack_from("!LQHH", payload)

        # Generate response struct
        response=av.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=copy.deepcopy(command.aecpdu_header),
            command_type=av.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY,
        )
 
        if descriptor_type == av.JDKSAVDECC_DESCRIPTOR_ENTITY:
            # we only support DESCRIPTOR_ENTITY
            controller_id = eui64_to_uint64(command.aecpdu_header.controller_entity_id)

            if aem_acquire_flags & 0x0000000001:
                # We don't currently handle the persistent flag
                pass
            
            if aem_acquire_flags & 0x8000000000:
                # Release controller if id matches
                if self.owner_entity_id == controller_id:
                    self.owner_entity_id = 0
                    status = av.JDKSAVDECC_AEM_STATUS_SUCCESS
                else:
                    # id doesn't match
                    status = av.JDKSAVDECC_AEM_STATUS_BAD_ARGUMENTS
            else:
                # Acquire controller
                if self.owner_entity_id:
                    # already acquired
                    status = av.JDKSAVDECC_AEM_STATUS_ENTITY_ACQUIRED
                else:
                    self.owner_entity_id = controller_id
                    status = av.JDKSAVDECC_AEM_STATUS_SUCCESS
                
            status = av.JDKSAVDECC_AEM_STATUS_SUCCESS
        else:
            status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

        # We build
        # av.struct_jdksavdecc_aem_command_acquire_entity_response
        # as payload
        resp_payload = struct.pack("!LQHH",
            aem_acquire_flags, # aem_acquire_flags
            self.owner_entity_id, # owner_entity_id
            descriptor_type, # descriptor_type
            descriptor_index, #descriptor_index
        )

        # Make it a response
        response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
        response.aecpdu_header.header.status = status
        
        logging.debug("ACQUIRE_ENTITY done")
        
        return response, resp_payload
        
    def lockEntity(self, command: av.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The lockEntity is used to handle the receipt, processing and respond to an LOCK_ENTITY AEM Command (7.4.2).
        The lockEntity function returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command LOCK_ENTITY

        logging.debug("LOCK_ENTITY")
        
        response = copy.deepcopy(command)
        response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
        response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE

        logging.debug("LOCK_ENTITY done")
        
        return response, bytes()
        
    def entityAvailable(self, command: av.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The lockEntity is used to handle the receipt, processing and respond to an LOCK_ENTITY AEM Command (7.4.2).
        The lockEntity function returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command ENTITY_AVAILABLE

        logging.debug("ENTITY_AVAILABLE")
        
        response = copy.deepcopy(command)
        response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
        response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE

        logging.debug("ENTITY_AVAILABLE done")
        
        return response, bytes()


    def processCommand(self, command: av.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The processCommand is used to handle the receipt, processing and respond to an AEM Command other than 
        ACQUIRE_ENTITY and LOCK_ENTITY.
        
        The processCommand function returns a AEMCommandResponse structure filled in with the appropriate details 
        from the command and an appropriate status code. 
        Any command that is received and not implemented shall be 
        responded to with a correctly sized response and a status of NOT_IMPLEMENTED.
        
        The AEMCommandResponse type (struct_jdksavdecc_aecpdu_common) is a structure containing the fields of a base AEM AECPDU.
        """
        # handle AEM Command other than ACQUIRE_ENTITY and LOCK_ENTITY

        response = None
        response_payload = None
        
        if command.command_type == av.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION:
            eid = eui64_to_uint64(command.aecpdu_header.controller_entity_id)
            self.unsolicited_list.add(eid)
            logging.debug(f"Added eid={eid} to unsolicited_list")

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response_payload = struct.pack("!L", 0)

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_DEREGISTER_UNSOLICITED_NOTIFICATION:
            eid = eui64_to_uint64(command.aecpdu_header.controller_entity_id)
            try:
                self.unsolicited_list.remove(eid)
                logging.debug(f"Removed eid={eid} from unsolicited_list")
                status = av.JDKSAVDECC_AEM_STATUS_SUCCESS
            except KeyError:
                status = av.JDKSAVDECC_AEM_STATUS_BAD_ARGUMENTS

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = status
            response_payload = struct.pack("!L", 0)

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_READ_DESCRIPTOR:
            em = self.entity_info
            _, _, descriptor_type, descriptor_index = struct.unpack_from("!4H", payload)
            configuration_index = 0 # need to adjust if more than one configuration

            logging.debug("READ_DESCRIPTOR %s", api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type))

            if descriptor_type == av.JDKSAVDECC_DESCRIPTOR_ENTITY:
                configuration_index = 0 # always 0
                descriptor = av.struct_jdksavdecc_descriptor_entity(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    entity_id=uint64_to_eui64(em.entity_id),
                    entity_model_id=uint64_to_eui64(em.entity_model_id),
                    entity_capabilities=em.entity_capabilities,
                    talker_stream_sources=em.talker_stream_sources,
                    talker_capabilities=em.talker_capabilities,
                    listener_stream_sinks=em.listener_stream_sinks,
                    listener_capabilities=em.listener_capabilities,
                    controller_capabilities=em.controller_capabilities,
                    available_index=em.available_index,
                    association_id=uint64_to_eui64(em.association_id),
                    entity_name=str_to_avstr("aesrl 16-channel"),
                    vendor_name_string=0,
                    model_name_string=0,
                    firmware_version=str_to_avstr("0.0"),
                    group_name=str_to_avstr("aesrl"),
                    serial_number=str_to_avstr("0.0"),
                    configurations_count=1,
                    current_configuration=0,
                )
                response_payload = pack_struct(descriptor)

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_CONFIGURATION:
                configuration_index = 0 # always 0
                descriptor = av.struct_jdksavdecc_descriptor_configuration(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=str_to_avstr("16 in"),
                    localized_description=0,
                    descriptor_counts_count=5,
                    descriptor_counts_offset=74,
                )
                descriptor_counts = struct.pack("!10H",
                    av.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_VIDEO_UNIT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SENSOR_UNIT, 0,
                    av.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_JACK_INPUT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_JACK_OUTPUT, 16,
                    av.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE, 1,
                    av.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_CONTROL, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_SIGNAL_SELECTOR, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_MIXER, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_MATRIX, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_LOCALE, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_MATRIX_SIGNAL, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_MEMORY_OBJECT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SIGNAL_SPLITTER, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SIGNAL_COMBINER, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SIGNAL_DEMULTIPLEXER, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SIGNAL_MULTIPLEXER, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SIGNAL_TRANSCODER, 0,
                    av.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_CONTROL_BLOCK, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_TIMING, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_PTP_INSTANCE, 0,
                )
                response_payload = pack_struct(descriptor)+descriptor_counts

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT:
                descriptor = av.struct_jdksavdecc_descriptor_audio_unit(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=av.struct_jdksavdecc_string(),
                    localized_description=0,
                    clock_domain_index=0,
                    number_of_stream_input_ports=2,
                    base_stream_input_port=0,
                    number_of_stream_output_ports=0,
                    base_stream_output_port=0,
                    number_of_external_input_ports=0,
                    base_external_input_port=0,
                    number_of_external_output_ports=16,
                    base_external_output_port=0,
                    number_of_internal_input_ports=0,
                    base_internal_input_port=0,
                    number_of_internal_output_ports=0,
                    base_internal_output_port=0,
                    number_of_controls=0,
                    base_control=0,
                    number_of_signal_selectors=0,
                    base_signal_selector=0,
                    number_of_mixers=0,
                    base_mixer=0,
                    number_of_matrices=0,
                    base_matrix=0,
                    number_of_splitters=0,
                    base_splitter=0,
                    number_of_combiners=0,
                    base_combiner=0,
                    number_of_demultiplexers=0,
                    base_demultiplexer=0,
                    number_of_multiplexers=0,
                    base_multiplexer=0,
                    number_of_transcoders=0,
                    base_transcoder=0,
                    number_of_control_blocks=0,
                    base_control_block=0,
                    current_sampling_rate=48000,
                    sampling_rates_offset=144,
                    sampling_rates_count=1,
                )
                sample_rates = struct.pack("!1L", 48000) # the 3 MSBs are used for a multiplier: 000 here, means multiplier 1.
                response_payload = pack_struct(descriptor)+sample_rates

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_INPUT:
                descriptor = av.struct_jdksavdecc_descriptor_stream_port(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    clock_domain_index=0,
                    port_flags=0x0001, # CLOCK_SYNC_SOURCE - Indicates that the Port can be used as a clock synchronization source.
#                               0x0002 + # ASYNC_SAMPLE_RATE_CONV - Indicates that the Port has an asynchronous sample rate con­vertor to convert sample rates between another Clock Domain and the Unit’s.
#                               0x0004, # SYNC_SAMPLE_RATE_CONV - Indicates that the Port has a synchronous sample rate convertor to convert between sample rates in the same Clock Domain.
                    number_of_controls=0,
                    base_control=0,
                    number_of_clusters=1,
                    base_cluster=descriptor_index,
                    number_of_maps=1,
                    base_map=descriptor_index,
                )
                response_payload = pack_struct(descriptor)

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT:
                descriptor = av.struct_jdksavdecc_descriptor_stream(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=str_to_avstr(f"Audio Input Stream {descriptor_index+1}"),
                    localized_description=0,
                    clock_domain_index=0,
                    stream_flags=av.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLOCK_SYNC_SOURCE +
                                    av.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLASS_A +
                                    0x8000,  # SUPPORTS_NO_SRP - new flag 
                    current_format=uint64_to_eui64(0x0205022002006000),
                    formats_offset=138,
                    number_of_formats=1, # N
                    backup_talker_entity_id_0=uint64_to_eui64(0),
                    backup_talker_unique_id_0=0,
                    backup_talker_entity_id_1=uint64_to_eui64(0),
                    backup_talker_unique_id_1=0,
                    backup_talker_entity_id_2=uint64_to_eui64(0),
                    backup_talker_unique_id_2=0,
                    backedup_talker_entity_id=uint64_to_eui64(0),
                    backedup_talker_unique=0,
                    avb_interface_index=0,
                    buffer_length=666,
                )
                formats = struct.pack("!3HQ",
                    138+8*1, # redundant_offset (138 + 8*N)
                    0, # number_of_redundant_streams R
                    0, # timing
                    # N stream formats
                    0x0205022002006000, # Standard/HC32 (48kHz, 32-bit int, 8 ch per frame, 6 smps per frame)
                    # R redundant streams
                )
                response_payload = pack_struct(descriptor)+formats

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE:
                descriptor = av.struct_jdksavdecc_descriptor_avb_interface(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=av.struct_jdksavdecc_string(),
                    localized_description=0,
                    mac_address=uint64_to_eui48(0x1007236de8b9),
                    interface_flags= \
#                        av.JDKSAVDECC_AVB_INTERFACE_FLAG_GPTP_GRANDMASTER_SUPPORTED +
                        av.JDKSAVDECC_AVB_INTERFACE_FLAG_GPTP_SUPPORTED,
#                       av.JDKSAVDECC_AVB_INTERFACE_FLAG_SRP_SUPPORTED,
                    clock_identity=uint64_to_eui64(self.entity_info.entity_id),
                    priority1=0,
                    clock_class=0,
                    offset_scaled_log_variance=0,
                    clock_accuracy=0,
                    priority2=0,
                    domain_number=0,
                    log_sync_interval=0,
                    log_announce_interval=0,
                    log_pdelay_interval=0,
                    port_number=0,
                    # IEEE Std 1722.1TM­2021 has two more members:
                    # number_of_controls (uint16)
                    # base_control (uint16)
                )
                response_payload = pack_struct(descriptor)
                
            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AUDIO_CLUSTER:
                ch_start = descriptor_index*8
                descriptor = av.struct_jdksavdecc_descriptor_audio_cluster(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=str_to_avstr(f"Channels {ch_start+1}-{ch_start+8} In"),
                    localized_description=0,
                    signal_type=av.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_INPUT,  # The descriptor_type for the signal source of the cluster.
                    signal_index=descriptor_index,  # The descriptor_index for the signal source of the cluster.
                    signal_output=0,
                    path_latency=0,
                    block_latency=0,
                    channel_count=8,
                    format=av.JDKSAVDECC_AUDIO_CLUSTER_FORMAT_MBLA,
                    PADDING_0=0,
                )
                response_payload = pack_struct(descriptor)
                
            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AUDIO_MAP:
                descriptor = av.struct_jdksavdecc_descriptor_audio_map(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    mappings_offset=8,
                    number_of_mappings=8, # N
                    # N mappings: !4H = (mapping_stream_index, mapping_stream_channel, mapping_cluster_offset, mapping_cluster_channel)
                )
                m = [(descriptor_index, c, 0, c) for c in range(8)]
                mappings = struct.pack("!32H", *flatten_list(m))
                response_payload = pack_struct(descriptor)+mappings
                
            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN:
                descriptor = av.struct_jdksavdecc_descriptor_clock_domain(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=str_to_avstr(""),
                    localized_description=0,
                    clock_source_index=0,
                    clock_sources_offset=76,
                    clock_sources_count=1, # C
                    # C*2: list of CLOCK_SOURCE descriptor indices
                )
                clk_sources = struct.pack("!H", 0)
                response_payload = pack_struct(descriptor)+clk_sources
                
            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE:
                descriptor = av.struct_jdksavdecc_descriptor_clock_source(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=str_to_avstr(""),
                    localized_description=0,
                    clock_source_flags=0x0001, # Table 7-16: LOCAL_ID
                    clock_source_type=0x0002, # Table 7-17: INPUT_STREAM
                    clock_source_identifier=uint64_to_eui64(0xffffffffffffffff),
                    clock_source_location_type=av.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN,
                    clock_source_location_index=0,
                )
                response_payload = pack_struct(descriptor)
                
            else:
                descriptor = None    
            
            if descriptor is not None:
                response = copy.deepcopy(command)
                response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
                response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_SUCCESS
                prefix = struct.pack("!2H", configuration_index, 0)
                response_payload = prefix+response_payload

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO:
            descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

            logging.debug("GET_AVB_INFO: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
#            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!2HQLBBH",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                0, # gptp_grandmaster_id
                0, # propagation_delay
                0, # gptp_domain_number
                0, # flags
                0, # msrp_mappings_count = N
                # N msrp_mappings "BBH" (traffic_class, priority, vlan_id)
            )

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_AS_PATH:
            descriptor_index, _ = struct.unpack_from("!2H", payload)

            logging.debug("GET_AS_PATH: descriptor_index=%d"%descriptor_index)

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
#            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!2HQ",
                descriptor_index, # descriptor_index
                1, # count
                self.entity_info.entity_id, # Grandmaster ID
            )

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_AUDIO_MAP:
            descriptor_type, descriptor_index, map_index, _ = struct.unpack_from("!4H", payload)

            logging.debug("GET_AUDIO_MAP: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!6H",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                map_index, # map_index
                2, # number_of_maps
                8, # number_of_mappings
                0, # reserved
                # N * Audio_mappings_format
            )

            m = [(descriptor_index, c, 0, c) for c in range(8)]
            mappings = struct.pack("!32H", *flatten_list(m))
            response_payload = pack_struct(descriptor) #+mappings

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_COUNTERS:
            descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

            logging.debug("GET_COUNTERS: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
#            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            if descriptor_type == av.JDKSAVDECC_DESCRIPTOR_ENTITY:
                counters_valid = 0

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE:
                counters_valid = 0

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN:
                counters_valid = 0

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT:
                counters_valid = 0

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT:
                counters_valid = 0

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_PTP_PORT:
                counters_valid = 0

            response_payload = struct.pack("!2HL",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                counters_valid, # counters_valid
            )+bytes(32*4)

        if response is None:
            response = copy.deepcopy(command.aecpdu_header)
            response.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
            
        return response, response_payload


    def txResponse(self, response, payload=None):
        """
        The txResponse function transmits an AEM response. 
        It sets the AEM AECPDU fields to the values from the response AEMCommandResponse parameter.
        """
        # transmits an AEM response. It sets the AEM AECPDU fields to the values from the response AEMCommandResponse parameter.
        for intf in self.interfaces:
            intf.send_aecp(response, payload)


    def run(self):
        logging.debug("EntityModelEntityStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_aecp_aem_cb(self.aecp_aem_cb)

        while True:
            self.unsolicited = None
            
            if self.rcvdCommand.empty():
                self.event.wait(1)
                # signalled
                self.event.clear()
                
            if self.doTerminate:
                break
            
            try:
                cmd, payload = self.rcvdCommand.get_nowait()
            except Empty:
                cmd = None
            
            try:
                if self.unsolicited is not None:
                    # UNSOLICITED RESPONSE
                    logging.debug("Unsolidated response")
                    self.unsolicited.sequence_id = self.unsolicitedSequenceID
                    self.txResponse(self.unsolicited)
                    self.unsolicitedSequenceID += 1
                    self.unsolicited = None
                
                if cmd is not None:
                    # RECEIVED COMMAND
                    response_payload = None
                    
                    if cmd.command_type == av.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY:
                        response, response_payload = self.acquireEntity(cmd, payload)
#                        pdb.set_trace()
                        
                    elif cmd.command_type == av.JDKSAVDECC_AEM_COMMAND_LOCK_ENTITY:
                        response, response_payload = self.lockEntity(cmd, payload)
                    elif cmd.command_type == av.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE:
                        response, response_payload = self.entityAvailable(cmd, payload)
                    else:
                        response, response_payload = self.processCommand(cmd, payload)
                    
                    if response is not None:
                        self.txResponse(response, response_payload)
                    else:
                        logging.warning("Response is None")
                    
            except Exception as e:
                traceback.print_exc();
#                logging.error("Exception: %s", e)

        for intf in self.interfaces:
            intf.unregister_aecp_aem_cb(self.aecp_aem_cb)

        logging.debug("EntityModelEntityStateMachine: Ending thread")


class AVDECC:

    def __init__(self, intf, entity_info, discover=False):
        self.intf = Interface(intf)
        
        # generate entity_id from MAC
        entity_id = eui64_to_uint64(mac_to_eid(self.intf.mac))
        
        # create EntityInfo
        self.entity_info = entity_info
        self.entity_info.entity_id = entity_id
        self.entity_info.gptp_grandmaster_id = entity_id

        self.state_machines = []

        # create InterfaceStateMachine
        adv_intf_sm = InterfaceStateMachine(
                             entity_info=self.entity_info,
                             interfaces=(self.intf,),
                             )
        self.state_machines.append(adv_intf_sm)
        
        # create AdvertisingEntityStateMachine
        adv_sm = AdvertisingEntityStateMachine(
                        entity_info=self.entity_info,
                        interface_state_machines=(adv_intf_sm,),
                        )
        self.state_machines.append(adv_sm)

        # create ACMPListenerStateMachine
        acmp_sm = ACMPListenerStateMachine(
                        entity_info=self.entity_info,
                        interfaces=(self.intf,),
                        )
        self.state_machines.append(acmp_sm)

        # create EntityModelEntityStateMachine
        aem_sm = EntityModelEntityStateMachine(entity_info=self.entity_info, interfaces=(self.intf,))
        self.state_machines.append(aem_sm)

    def __enter__(self):
        logging.debug("Starting threads")
        for sm in self.state_machines:
            sm.start()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if not issubclass(exception_type, KeyboardInterrupt):
            print("Exception:", exception_value)

        logging.debug("Trying to join threads")
        for sm in self.state_machines:
            sm.performTerminate()
        # wait for termination
        while sum(sm.is_alive() for sm in self.state_machines):
            time.sleep(0.001)

        logging.debug("Successfully joined threads")


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-i", "--intf", type=str, default='eth0',
                        help="Network interface (default='%(default)s')")
    parser.add_argument("-v", "--valid", type=float, default=62, help="Valid time in seconds (default=%(default)s)")
    parser.add_argument("--discover", action='store_true', help="Discover AVDECC entities")
    parser.add_argument('-d', "--debug", action='store_true', default=0,
                        help="Enable debug mode")
#    parser.add_argument('-v', "--verbose", action='count', default=0,
#                        help="Increase verbosity")
#    parser.add_argument("args", nargs='*')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        
    entity_info = EntityInfo(
        valid_time=args.valid,
        entity_model_id = 3,
        entity_capabilities=av.JDKSAVDECC_ADP_ENTITY_CAPABILITY_AEM_SUPPORTED +
                            av.JDKSAVDECC_ADP_ENTITY_CAPABILITY_CLASS_A_SUPPORTED +
                            av.JDKSAVDECC_ADP_ENTITY_CAPABILITY_GPTP_SUPPORTED,
        listener_stream_sinks=2,
        listener_capabilities=av.JDKSAVDECC_ADP_LISTENER_CAPABILITY_IMPLEMENTED +
                              av.JDKSAVDECC_ADP_LISTENER_CAPABILITY_AUDIO_SINK,
    )

    with AVDECC(intf=args.intf, entity_info=entity_info, discover=args.discover) as avdecc:

        while(True):
            time.sleep(0.1)
