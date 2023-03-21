#!/usr/bin/env python3

import ctypes
import avdecc_api
from avdecc_api import AVDECC_create, AVDECC_destroy, AVDECC_send_adp, AVDECC_set_adpdu, AVDECC_send_acmp, AVDECC_send_aecp
import time
import logging
from threading import Thread, Event
import random


def eui64_str(eui64):
    return ":".join(f"{x:02x}" for x in eui64.value)

def adpdu_header_str(hdr):
    return "cd={:x} subtype={:x} sv={:x} version={:x} message_type={:x} " \
           "valid_time={:x} control_data_length={} entity_id={}".format(
        hdr.cd,
        hdr.subtype,
        hdr.sv,
        hdr.version,
        hdr.message_type,
        hdr.valid_time,
        hdr.control_data_length,
        eui64_str(hdr.entity_id),
    )

def adpdu_str(adpdu):
    return "hdr=[{}] entity_model_id={} entity_capabilities={:x} " \
           "talker_stream_sources={} talker_capabilities={:x} " \
           "listener_stream_sinks={} listener_capabilities={:x} " \
           "controller_capabilities={:x} available_index={:x} " \
           "gptp_grandmaster_id={} gptp_domain_number={:x} " \
           "identify_control_index={:x} interface_index={:x} " \
           "association_id={}".format(
        adpdu_header_str(adpdu.header),
        eui64_str(adpdu.entity_model_id),
        adpdu.entity_capabilities,
        adpdu.talker_stream_sources,
        adpdu.talker_capabilities,
        adpdu.listener_stream_sinks,
        adpdu.listener_capabilities,
        adpdu.controller_capabilities,
        adpdu.available_index,
        eui64_str(adpdu.gptp_grandmaster_id),
        adpdu.gptp_domain_number,
        adpdu.identify_control_index,
        adpdu.interface_index,
        eui64_str(adpdu.association_id),
    )

def aecpdu_aem_header_str(hdr):
    return "cd={:x} subtype={:x} sv={:x} version={:x} message_type={:x} " \
           "status={:x} control_data_length={} target_entity_id={}".format(
        hdr.cd,
        hdr.subtype,
        hdr.sv,
        hdr.version,
        hdr.message_type,
        hdr.status,
        hdr.control_data_length,
        eui64_str(hdr.target_entity_id),
    )

def aecpdu_aem_str(aecpdu_aem):
    return "hdr=[{}] controller_entity_id={} sequence_id={} command_type={:x}".format(
        aecpdu_aem_header_str(aecpdu_aem.aecpdu_header.header),
        eui64_str(aecpdu_aem.aecpdu_header.controller_entity_id),
        aecpdu_aem.aecpdu_header.sequence_id,
        aecpdu_aem.command_type,
    )


def uint64_to_eui64(other):
    return (
        ( other >> ( 7 * 8 ) ) & 0xff,
        ( other >> ( 6 * 8 ) ) & 0xff,
        ( other >> ( 5 * 8 ) ) & 0xff,
        ( other >> ( 4 * 8 ) ) & 0xff,
        ( other >> ( 3 * 8 ) ) & 0xff,
        ( other >> ( 2 * 8 ) ) & 0xff,
        ( other >> ( 1 * 8 ) ) & 0xff,
        ( other >> ( 0 * 8 ) ) & 0xff
    )

def eui64_to_uint64(value):
    return ( value[0] << ( 7 * 8 ))+
           ( value[1] << ( 6 * 8 ))+
           ( value[2] << ( 5 * 8 ))+
           ( value[3] << ( 4 * 8 ))+
           ( value[4] << ( 3 * 8 ))+
           ( value[5] << ( 2 * 8 ))+
           ( value[6] << ( 1 * 8 ))+
           ( value[7] << ( 0 * 8 ))


class EntityInfo:
    """
    IEEE 1722.1-2021, section 6.2.7
    """

    def __init__(self, 
                 valid_time=62,
                 entity_id=None,
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
        self.valid_time = valid_time # MacOS standard
        self.entity_id = entity_id or self.entityID_from_mac(mac_address)
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
        return avdecc_api.struct_jdksavdecc_adpdu(
            header = avdecc_api.struct_jdksavdecc_adpdu_common_control_header(
                valid_time=max(0,min(int(self.valid_time/2.+0.5),31)),
            ),
            entity_id=self.entity_id,
            entity_model_id = avdecc_api.struct_jdksavdecc_eui64(
                value=uint64_to_eui64(self.entity_model_id),
            ),
            entity_capabilities=self.entity_capabilities,
            talker_stream_sources=self.talker_stream_sources,
            talker_capabilities=self.talker_capabilities,
            listener_stream_sinks=self.listener_stream_sinks,
            listener_capabilities=self.listener_capabilities,
            controller_capabilities=self.controller_capabilities,
            available_index=self.available_index,
            gptp_grandmaster_id=self.gptp_grandmaster_id,
            gptp_domain_number=self.gptp_domain_number,
            current_configuration_index=self.current_configuration_index,
            identify_control_index=self.identify_control_index,
            interface_index=self.interface_index,
            association_id=self.association_id,
        )


#def entityID_from_mac(mac_address):
#    raise NotImplementedError()


class Interface:
    def __init__(self, ifname):
        self.ifname = ifname


class GlobalStateMachine:
    """
    IEEE 1722.1-2021, section 6.2.3
    """
    def __init__(self):
        self.entityInfo = EntityInfo()
        
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
        self.super(AdvertisingEntityStateMachine).__init__(entity_info)
        self.reannouncementTimerTimeout = 0
        self.needsAdvertise = False
        self.doTerminate = False
        self.event = Event()
        self.random = random.Random(
            seed=self.entityInfo.mac_address+int(self.currentTime*10**6)
        )
        self.interface_state_machines = interface_state_machines

    def performAdvertise(self):
        self.needsAdvertise = True
        self.event.set()

    def performTerminate(self):
        self.doTerminate = True
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
        return self.random.uniform(0, self.entityInfo.valid_time/5.)

    def run(self):
        self.entity_info.available_index = 0

        while True:
            self.event.wait(self.randomDeviceDelay())
            if self.doTerminate:
                break
            self.event.clear()

            self.sendAvailable()

            self.needsAdvertise = False

            self.event.wait(max(1, self.entityInfo.valid_time/2))
            if self.doTerminate:
                break
            self.event.clear()

            self.entityInfo.available_index += 1


class AdvertisingInterfaceStateMachine(Thread):
    """
    IEEE 1722.1-2021, section 6.2.5
    
    for each AVB interface of the ATDECC Entity being published in the End Station
    """
    
    def __init__(self, interfaces):
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
        raise NotImplementedError()

    def txEntityDeparting(self):
        """
        The txEntityAvailable function transmits an ENTITY_DEPARTING message
        """
        raise NotImplementedError()

    def run(self):
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
        self.currentGrandmasterID = None
        self.advertisedGrandmasterID = None
        self.rcvdDiscover = None
        self.entityID = 0
        self.linkIsUp = False
        self.lastLinkIsUp = False
        self.currentConfigurationIndex = None
        self.advertisedConfigurationIndex = None
        self.event = Event()
        
    def run(self):
        self.lastLinkIsUp = False
        self.advertisedGrandmasterID = self.currentGrandmasterID
        
        while True:
            self.event.wait()
            self.event.clear()
            
            if self.rcvdDiscover:
                # RECEIVED DISCOVER
                self.rcvdDiscover = False
                
                if entity_id == 0 || entity_id == entityInfo.entity_id:
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


class AVDECC:
    handles = {}

    def __init__(self, intf, entity=0, discover=False, debug=False):
        self.intf = intf
        self.debug = debug
        self.discover = discover
        self.handle = ctypes.c_void_p()
        self.entity = entity
        self.available_index = 0

    def __enter__(self):
        intf = ctypes.c_char_p(self.intf.encode())
        res = AVDECC_create(ctypes.byref(self.handle), intf, AVDECC._adp_cb, AVDECC._acmp_cb, AVDECC._aecp_aem_cb)
        assert res == 0
        logging.debug("AVDECC_create done")
        AVDECC.handles[self.handle.value] = self  # register instance

        adpdu = avdecc_api.struct_jdksavdecc_adpdu(
            header = avdecc_api.struct_jdksavdecc_adpdu_common_control_header(
                valid_time = 31,
            ),
            entity_model_id = avdecc_api.struct_jdksavdecc_eui64(value=(1,2,3,4,5,6,7,8)),
            entity_capabilities=avdecc_api.JDKSAVDECC_ADP_ENTITY_CAPABILITY_CLASS_A_SUPPORTED +
                                avdecc_api.JDKSAVDECC_ADP_ENTITY_CAPABILITY_GPTP_SUPPORTED,
            listener_stream_sinks=16,
            listener_capabilities=avdecc_api.JDKSAVDECC_ADP_LISTENER_CAPABILITY_IMPLEMENTED +
                                  avdecc_api.JDKSAVDECC_ADP_LISTENER_CAPABILITY_AUDIO_SINK,
            gptp_grandmaster_id=avdecc_api.struct_jdksavdecc_eui64(value=(1,2,3,4,5,6,7,8)),
            available_index = self.available_index,
        )
        res = AVDECC_set_adpdu(self.handle, adpdu)
        logging.debug("AVDECC_set_adpdu done")
        assert res == 0

        self.send_adp(avdecc_api.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_AVAILABLE, self.entity)
        self.available_index += 1

        if self.discover:
            self.send_adp(avdecc_api.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER, 0)

        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if not issubclass(exception_type, KeyboardInterrupt):
            print("Exception:", exception_value)

        self.send_adp(avdecc_api.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity)

        # we need a bit of time so that the previous message can get through
        time.sleep(0.5)

        self.available_index = 0

        res = AVDECC_destroy(self.handle)
        logging.debug("AVDECC_destroy done")
        assert res == 0
        del AVDECC.handles[self.handle.value]  # unregister instance
        self.handle.value = None

    def send_adp(self, msg, entity):
        res = AVDECC_send_adp(self.handle, msg, entity)
        logging.debug(f"AVDECC_send_adp {msg} done")
        assert res == 0

    def recv_adp(self, adpdu):
        print("ADP:", adpdu_str(adpdu))

    def recv_acmp(self, acmpdu):
        print("ACMP:", acmpdu)

    def recv_aecp_aem(self, aecpdu_aem):
        print("AECP_AEM:", aecpdu_aem_str(aecpdu_aem))

    @avdecc_api.AVDECC_ADP_CALLBACK
    def _adp_cb(handle, frame_ptr, adpdu_ptr):
        AVDECC.handles[handle].recv_adp(adpdu_ptr.contents)

    @avdecc_api.AVDECC_ACMP_CALLBACK
    def _acmp_cb(handle, frame_ptr, acmpdu_ptr):
        AVDECC.handles[handle].recv_acmp(acmpdu_ptr.contents)

    @avdecc_api.AVDECC_AECP_AEM_CALLBACK
    def _aecp_aem_cb(handle, frame_ptr, aecpdu_aem_ptr):
        AVDECC.handles[handle].recv_acecp_aem(aecpdu_aem_ptr.contents)


def chk_err(res):
    if res:
        raise RuntimeError("Error", res)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-i", "--intf", type=str, default='eth0',
                        help="Network interface (default='%(default)s')")
    parser.add_argument("-e", "--entity", type=int, default=0x1122334455667788,
                        help="Entity ID (default='%(default)x')")
    parser.add_argument("--discover", action='store_true', help="Discover AVDECC entities")
    parser.add_argument('-d', "--debug", action='store_true', default=0,
                        help="Enable debug mode")
#    parser.add_argument('-v', "--verbose", action='count', default=0,
#                        help="Increase verbosity")
#    parser.add_argument("args", nargs='*')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    with AVDECC(intf=args.intf, entity=args.entity, discover=args.discover) as avdecc:

        while(True):
            time.sleep(0.1)
