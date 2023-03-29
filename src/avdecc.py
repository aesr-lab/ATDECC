#!/usr/bin/env python3

import ctypes
import struct
import avdecc_api as av
from avdecc_api import AVDECC_create, AVDECC_destroy, AVDECC_send_frame, AVDECC_send_adp, AVDECC_set_adpdu, AVDECC_send_acmp, AVDECC_send_aecp
import time
import logging
from threading import Thread, Event
import random
import netifaces


api_dicts = {}

def get_api_dict(enum_dict):
    try:
        return api_dicts[enum_dict]
    except KeyError:
        pass
    d = []
    for k in av.__dict__.keys():
        if k.startswith('e_'+enum_dict) and k.endswith("__enumvalues"):
            d.append(k)
    ed = [av.__dict__[di] for di in d]
    api_dicts[enum_dict] = ed
    return ed 


def api_enum(enum_dict, ix):
    dct = get_api_dict(enum_dict)
    for di in dct:
        try:
            return di[ix].replace(enum_dict, '')
        except KeyError:
            pass
    raise KeyError()


def eui_to_str(eui):
    return ":".join(f"{x:02x}" for x in eui.value)


def adpdu_header_str(hdr):
    return "cd={:x} subtype={:x} sv={:x} version={:x} message_type={} " \
           "valid_time={} control_data_length={} entity_id={}".format(
        hdr.cd,
        hdr.subtype,
        hdr.sv,
        hdr.version,
        api_enum('JDKSAVDECC_ADP_MESSAGE_TYPE_', hdr.message_type),
        hdr.valid_time,
        hdr.control_data_length,
        eui_to_str(hdr.entity_id),
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
        eui_to_str(adpdu.entity_model_id),
        adpdu.entity_capabilities,
        adpdu.talker_stream_sources,
        adpdu.talker_capabilities,
        adpdu.listener_stream_sinks,
        adpdu.listener_capabilities,
        adpdu.controller_capabilities,
        adpdu.available_index,
        eui_to_str(adpdu.gptp_grandmaster_id),
        adpdu.gptp_domain_number,
        adpdu.identify_control_index,
        adpdu.interface_index,
        eui_to_str(adpdu.association_id),
    )


def acmpdu_header_str(hdr):
    return "cd={:x} subtype={:x} sv={:x} version={:x} message_type={} " \
           "status={:x} control_data_length={} stream_id={}".format(
        hdr.cd,
        hdr.subtype,
        hdr.sv,
        hdr.version,
        api_enum('JDKSAVDECC_ACMP_MESSAGE_TYPE_', hdr.message_type),
        hdr.status,
        hdr.control_data_length,
        eui_to_str(hdr.stream_id),
    )


def acmpdu_str(acmpdu):
    return "hdr=[{}] controller_entity_id={} talker_entity_id={} " \
           "listener_entity_id={} talker_unique_id={:x} " \
           "listener_unique_id={:x} stream_dest_mac={} " \
           "connection_count={} sequence_id={} flags={:x} stream_vlan_id={:x}".format(
        acmpdu_header_str(acmpdu.header),
        eui_to_str(acmpdu.controller_entity_id),
        eui_to_str(acmpdu.talker_entity_id),
        eui_to_str(acmpdu.listener_entity_id),
        acmpdu.talker_unique_id,
        acmpdu.listener_unique_id,
        eui_to_str(acmpdu.stream_dest_mac),
        acmpdu.connection_count,
        acmpdu.sequence_id,
        acmpdu.flags,
        acmpdu.stream_vlan_id,
    )


def aecpdu_aem_header_str(hdr):
    return "cd={:x} subtype={:x} sv={:x} version={:x} message_type={} " \
           "status={} control_data_length={} target_entity_id={}".format(
        hdr.cd,
        hdr.subtype,
        hdr.sv,
        hdr.version,
        api_enum('JDKSAVDECC_AECP_MESSAGE_TYPE_', hdr.message_type),
        api_enum('JDKSAVDECC_ACMP_STATUS_', hdr.status),
        hdr.control_data_length,
        eui_to_str(hdr.target_entity_id),
    )

def aecpdu_aem_str(aecpdu_aem):
    return "hdr=[{}] controller_entity_id={} sequence_id={} command_type={}".format(
        aecpdu_aem_header_str(aecpdu_aem.aecpdu_header.header),
        eui_to_str(aecpdu_aem.aecpdu_header.controller_entity_id),
        aecpdu_aem.aecpdu_header.sequence_id,
        api_enum('JDKSAVDECC_AEM_COMMAND_', aecpdu_aem.command_type),
    )


def uint64_to_eui64(other):
    v = av.struct_jdksavdecc_eui64()
    v.value[:] = (
        ( other >> ( 7 * 8 ) ) & 0xff,
        ( other >> ( 6 * 8 ) ) & 0xff,
        ( other >> ( 5 * 8 ) ) & 0xff,
        ( other >> ( 4 * 8 ) ) & 0xff,
        ( other >> ( 3 * 8 ) ) & 0xff,
        ( other >> ( 2 * 8 ) ) & 0xff,
        ( other >> ( 1 * 8 ) ) & 0xff,
        ( other >> ( 0 * 8 ) ) & 0xff
    )
    return v


def eui64_to_uint64(v):
    return ( v.value[0] << ( 7 * 8 ))+ \
           ( v.value[1] << ( 6 * 8 ))+ \
           ( v.value[2] << ( 5 * 8 ))+ \
           ( v.value[3] << ( 4 * 8 ))+ \
           ( v.value[4] << ( 3 * 8 ))+ \
           ( v.value[5] << ( 2 * 8 ))+ \
           ( v.value[6] << ( 1 * 8 ))+ \
           ( v.value[7] << ( 0 * 8 ))


def uint64_to_eui48(other):
    assert ( other >> ( 6 * 8 ) ) == 0
    v = av.struct_jdksavdecc_eui48()
    v.value[:] = (
        ( other >> ( 5 * 8 ) ) & 0xff,
        ( other >> ( 4 * 8 ) ) & 0xff,
        ( other >> ( 3 * 8 ) ) & 0xff,
        ( other >> ( 2 * 8 ) ) & 0xff,
        ( other >> ( 1 * 8 ) ) & 0xff,
        ( other >> ( 0 * 8 ) ) & 0xff
    )
    return v


def eui48_to_uint64(v):
    return ( v.value[0] << ( 5 * 8 ))+ \
           ( v.value[1] << ( 4 * 8 ))+ \
           ( v.value[2] << ( 3 * 8 ))+ \
           ( v.value[3] << ( 2 * 8 ))+ \
           ( v.value[4] << ( 1 * 8 ))+ \
           ( v.value[5] << ( 0 * 8 ))


def mac_to_eui64(mac):
    # see https://www.geeksforgeeks.org/ipv6-eui-64-extended-unique-identifier/
    if type(mac) is int: #uint64 format
        mac = uint64_to_eui48(mac)
    elif type(mac) is str:
        if ':' in mac:
            mac = mac.split(':')
        elif '-' in mac:
            mac = mac.split('-')
        else:
            raise ValueError('Mac address format unknown')
        # convert hex digits to ints
        mac = [int(m, 16) for m in mac]
    elif type(mac) not in ('list', 'tuple'):
        raise TypeError('Mac address data type unknown')

    v = av.struct_jdksavdecc_eui64()
    v.value[:] = (mac[0]^0x02, mac[1], mac[2], 0xff, 0xf0, mac[3], mac[4], mac[5])
    return v


def mac_to_uint64(mac):
    return eui64_to_uint64(mac_to_eui64(mac))


def intf_to_mac(intf):
    """
    return MAC of network interface (raises exception if not available)
    """
    addrs = netifaces.ifaddresses(intf)
    return addrs[netifaces.AF_LINK][0]['addr']


def intf_to_ip(intf):
    """
    return IP of network interface (raises exception if not available)
    """
    addrs = netifaces.ifaddresses(intf)
    return addrs[netifaces.AF_INET][0]['addr']


def jdksavdecc_validate_range(bufpos: int, buflen: int, elem_size: int) -> int:
    return bufpos+elem_size if bufpos+elem_size <= buflen else -1

def jdksavdecc_eui64_set(v, base, pos: int):
    base[pos:pos+8] = v.value

def jdksavdecc_uint64_set(v, base, pos: int):
    struct.pack_into('!Q', base, pos, v)

def jdksavdecc_uint32_set(v, base, pos: int):
    struct.pack_into('!L', base, pos, v)

def jdksavdecc_uint16_set(v, base, pos: int):
    struct.pack_into('!H', base, pos, v)

def jdksavdecc_uint8_set(v, base, pos: int):
    struct.pack_into('!B', base, pos, v)

def jdksavdecc_subtype_data_set_cd( v, base, pos: int ):
    base[pos] = ( base[pos] & 0x7f ) | ( 0x80 if v else 0x00 )

def jdksavdecc_common_control_header_set_subtype( v, base, pos: int ):
    base[pos] = ( base[pos] & 0x80 ) | ( v & 0x7f )

def jdksavdecc_subtype_data_set_sv( v, base, pos: int ):
    base[pos+1] = ( base[pos+1] & 0x7f ) | ( 0x80 if v else 0x00 )

def jdksavdecc_subtype_data_set_version( v, base, pos: int ):
    base[pos+1] = ( base[pos+1] & 0x8f ) | ( ( v & 0x7 ) << 4 )

def jdksavdecc_avtp_subtype_data_set_control_data( v, base, pos: int ):
    base[pos+1] = ( base[pos+1] & 0xf0 ) | ( ( v & 0xf ) << 0 )

def jdksavdecc_subtype_data_set_status( v, base, pos: int ):
    base[pos+2] = ( base[pos+2] & 0x07 ) | ( ( v & 0x1f ) << 3 )

def jdksavdecc_subtype_data_set_control_data_length( v, base, pos: int ):
    base[pos+2] = ( base[pos+2] & 0xf8 ) + ( ( v >> 8 ) & 0x07 )
    base[pos+3] = ( v & 0xff )


def jdksavdecc_adpdu_common_control_header_write( p: av.struct_jdksavdecc_adpdu_common_control_header,
                                            base,
                                            pos: int,
                                            ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN )
    if r >= 0:
        jdksavdecc_subtype_data_set_cd( p.cd, base, pos )
        jdksavdecc_common_control_header_set_subtype( p.subtype, base, pos )
        jdksavdecc_subtype_data_set_sv( p.sv, base, pos)
        jdksavdecc_subtype_data_set_version( p.version, base, pos)
        jdksavdecc_avtp_subtype_data_set_control_data ( p.message_type, base, pos)
        jdksavdecc_subtype_data_set_status( p.valid_time, base, pos)
        jdksavdecc_subtype_data_set_control_data_length( p.control_data_length, base, pos)
        jdksavdecc_eui64_set( p.entity_id, base, pos + av.JDKSAVDECC_COMMON_CONTROL_HEADER_OFFSET_STREAM_ID )
    return r


def jdksavdecc_adpdu_write( p: av.struct_jdksavdecc_adpdu , 
                            base, 
                            pos: int, 
                            ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_ADPDU_LEN )
    if r >= 0:
        jdksavdecc_adpdu_common_control_header_write( p.header, base, pos, ln )
        jdksavdecc_eui64_set( p.entity_model_id, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_ENTITY_MODEL_ID )
        jdksavdecc_uint32_set( p.entity_capabilities, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_ENTITY_CAPABILITIES )
        jdksavdecc_uint16_set( p.talker_stream_sources, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_TALKER_STREAM_SOURCES )
        jdksavdecc_uint16_set( p.talker_capabilities, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_TALKER_CAPABILITIES )
        jdksavdecc_uint16_set( p.listener_stream_sinks, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_LISTENER_STREAM_SINKS )
        jdksavdecc_uint16_set( p.listener_capabilities, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_LISTENER_CAPABILITIES )
        jdksavdecc_uint32_set( p.controller_capabilities, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_CONTROLLER_CAPABILITIES )
        jdksavdecc_uint32_set( p.available_index, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_AVAILABLE_INDEX )
        jdksavdecc_eui64_set( p.gptp_grandmaster_id, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_GPTP_GRANDMASTER_ID )
        jdksavdecc_uint8_set( p.gptp_domain_number, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_GPTP_DOMAIN_NUMBER )
        jdksavdecc_uint8_set( p.reserved0, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_RESERVED0 )
        jdksavdecc_uint16_set( p.identify_control_index, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_IDENTIFY_CONTROL_INDEX )
        jdksavdecc_uint16_set( p.interface_index, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_INTERFACE_INDEX )
        jdksavdecc_eui64_set( p.association_id, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_ASSOCIATION_ID )
        jdksavdecc_uint32_set( p.reserved1, base, pos + av.JDKSAVDECC_ADPDU_OFFSET_RESERVED1 )
    return r


def adp_form_msg( adpdu: av.struct_jdksavdecc_adpdu,
                  message_type: av.uint16_t,
                  target_entity: av.struct_jdksavdecc_eui64  ) -> av.struct_jdksavdecc_frame:
    adpdu.header.cd = 1
    adpdu.header.subtype = av.JDKSAVDECC_SUBTYPE_ADP
    adpdu.header.version = 0
    adpdu.header.sv = 0
    adpdu.header.control_data_length = av.JDKSAVDECC_ADPDU_LEN - av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    adpdu.header.message_type = message_type
    adpdu.header.entity_id = target_entity
    frame = av.struct_jdksavdecc_frame(
        ethertype = av.JDKSAVDECC_AVTP_ETHERTYPE,
        dest_address = uint64_to_eui48(av.JDKSAVDECC_MULTICAST_ADP_ACMP_MAC),
    )
    frame.length = jdksavdecc_adpdu_write( adpdu, frame.payload, 0, len(frame.payload) )
    return frame


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
        logging.debug(f"AVDECC_send_adp {msg} done")

    def send_aecp_aem(self, pdu, entity):
        res = AVDECC_set_aecpdu_aem(self.handle, pdu)
        assert res == 0
        res = AVDECC_send_adp(self.handle, msg, av.uint64_t(entity.entity_id))
        assert res == 0
        logging.debug(f"AVDECC_send_adp {msg} done")

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
        if len(this.aecp_aem_cbs) == 0:
            logging.debug("Unhandled AECP_AEM: %s", aecpdu_aem_str(du))
        else:
            for cb in this.aecp_aem_cbs:
                cb(du)


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

            self.entity_info.available_index += 1

        logging.debug("AdvertisingEntityStateMachine: Ending thread")


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
        self.rcvdDiscover = None
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

    def txEntityDeparting(self):
        """
        The txEntityAvailable function transmits an ENTITY_DEPARTING message
        """
        for intf in self.interfaces:
            intf.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity_info)

    def adp_cb(self, adpdu):
        logging.info("ADP: %s", adpdu_str(adpdu))
        
        if adpdu.header.message_type == av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER:
            self.rcvdDiscover = adpdu.header.entity_id
        
    def run(self):
        logging.debug("InterfaceStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_adp_cb(self.adp_cb)

        while True:
            self.event.wait(1)
            # signalled
            if self.doTerminate:
                break
            self.event.clear()
            
            # AdvertisingInterfaceStateMachine
            if self.doAdvertise:
                self.txEntityAvailable()
                self.doAdvertise = False
                
            # DiscoveryInterfaceStateMachine
            if self.rcvdDiscover is not None:
                # RECEIVED DISCOVER
                if self.rcvdDiscover == 0 or self.rcvdDiscover == self.entityInfo.entity_id:
                    # DISCOVER
                    logging.debug("Respond to Discover")
                    self.performAdvertise()
                    
                self.rcvdDiscover = None
            
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

    def acmp_cb(self, acmpdu):
        if acmpdu.listener_entity_id == self.my_id:
            logging.info("ACMP: %s", acmp_str(acmpdu))

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
            
            self.event.wait(1)
            # signalled
            if self.doTerminate:
                break
            self.event.clear()
            
            # check timeouts
            ct = self.currentTime
            retried = []
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
            

        for intf in self.interfaces:
            intf.unregister_acmp_cb(self.acmp_cb)

        logging.debug("ACMPListenerStateMachine: Ending thread")


class EntityModelEntityStateMachine(Thread):
    """
    IEEE 1722.1-2021, section 9.3.5
    """
    
    def __init__(self, entity_info, interfaces):
        super(EntityModelEntityStateMachine, self).__init__()
        self.event = Event()
        self.doTerminate = False
        self.interfaces = interfaces
        
        self.rcvdCommand = None
        self.myEntityID = entity_info.entity_id
        self.unsolicited = None
        self.unsolicitedSequenceID = 0
        
    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()
        
    def aecp_aem_cb(self, aecp_aemdu):
        if aecp_aemdu.aecpdu_header.header.target_entity_id == self.myEntityID:
            logging.info("AECP AEM: %s", aecpdu_aem_str(aecp_aemdu))

            if aecp_aemdu.aecpdu_header.header.message_type == av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND:
                self.rcvdCommand = aecp_aemdu
                self.event.set()

    def acquireEntity(self, command):
        """
        The acquireEntity function is used to handle the receipt, processing and respond to an ACQUIRE_ENTITY AEM Command (7.4.1).
        
        The acquireEntity function handles checking the current status of the acquisition, issuing any required 
        CONTROLLER_AVAILABLE AEM Command (7.4.4) and dealing with the response and sending any required IN_PROGRESS responses 
        for the passed in command.
        acquireEntity returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command ACQUIRE_ENTITY
        
        raise NotImplementedError()
        
        response = struct_jdksavdecc_aem_command_acquire_entity_response(
            aem_header=struct_jdksavdecc_aecpdu_aem(
                command_type=av.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
            ),
            aem_acquire_flags=0,
            owner_entity_id=self.myEntityID,
            descriptor_type=0,
            descriptor_index=0,
        )
        return response
        
    def lockEntity(self, command):
        """
        The lockEntity is used to handle the receipt, processing and respond to an LOCK_ENTITY AEM Command (7.4.2).
        The lockEntity function returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command LOCK_ENTITY 
        raise NotImplementedError()
        
    def processCommand(self, command):
        """
        The processCommand is used to handle the receipt, processing and respond to an AEM Command other than 
        ACQUIRE_ENTITY and LOCK_ENTITY.
        The processCommand function returns a AEMCommandResponse structure filled in with the appropriate details 
        from the command and an appropriate status code. Any command that is received and not implemented shall be 
        responded to with a correctly sized response and a status of NOT_IMPLEMENTED.
        """
        # handle AEM Command other than ACQUIRE_ENTITY and LOCK_ENTITY
        raise NotImplementedError()
        
    def txResponse(self, response):
        """
        The txResponse function transmits an AEM response. 
        It sets the AEM AECPDU fields to the values from the response AEMCommandResponse parameter.
        """
        # transmits an AEM response. It sets the AEM AECPDU fields to the values from the response AEMCommandResponse parameter.
        for intf in self.interfaces:
            intf.send_aecp_aem(response, self.entity_info)


    def run(self):
        logging.debug("EntityModelEntityStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_aecp_aem_cb(self.aecp_aem_cb)

        while True:
            self.rcvdCommand = None
            self.rcvdId = 0
            self.unsolicited = None
            
            self.event.wait(1)
            # signalled
            if self.doTerminate:
                break
            self.event.clear()
            
            if self.unsolicited is not None:
                # UNSOLICITED RESPONSE
                logging.debug("Unsolidated response")
                self.unsolicited.sequence_id = self.unsolicitedSequenceID
                self.txResponse(self.unsolicited)
                self.unsolicitedSequenceID += 1
                self.unsolicited = None
                
            if self.rcvdCommand is not None:
                # RECEIVED COMMAND
                logging.debug("Received command")
                if self.rcvdCommand.command_type == av.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY:
                    response = self.acquireEntity(rcvdCommand)
                elif self.rcvdCommand.command_type == av.JDKSAVDECC_AEM_COMMAND_LOCK_ENTITY:
                    response = self.lockEntity(rcvdCommand)
                elif self.rcvdCommand.command_type == av.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE:
                    response = self.rcvdCommand
                else:
                    response = self.processCommand(self.rcvdCommand)
                self.txResponse(response)
                self.rcvdCommand = None

        for intf in self.interfaces:
            intf.unregister_aecp_aem_cb(self.aecp_aem_cb)

        logging.debug("EntityModelEntityStateMachine: Ending thread")


class AVDECC:

    def __init__(self, intf, valid_time=62, discover=False):
        self.intf = Interface(intf)
        
        # generate entity_id from MAC
        entity_id = mac_to_uint64(self.intf.mac)
        
        # create EntityInfo
        self.entity_info = EntityInfo(entity_id=entity_id, valid_time=valid_time)

        self.state_machines = []

        # create AdvertisingInterfaceStateMachine
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


class xxAVDECC:
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

        adpdu = av.struct_jdksavdecc_adpdu(
            header = av.struct_jdksavdecc_adpdu_common_control_header(
                valid_time = 31,
            ),
            entity_model_id = av.struct_jdksavdecc_eui64(value=(1,2,3,4,5,6,7,8)),
            entity_capabilities=av.JDKSAVDECC_ADP_ENTITY_CAPABILITY_CLASS_A_SUPPORTED +
                                av.JDKSAVDECC_ADP_ENTITY_CAPABILITY_GPTP_SUPPORTED,
            listener_stream_sinks=16,
            listener_capabilities=av.JDKSAVDECC_ADP_LISTENER_CAPABILITY_IMPLEMENTED +
                                  av.JDKSAVDECC_ADP_LISTENER_CAPABILITY_AUDIO_SINK,
            gptp_grandmaster_id=av.struct_jdksavdecc_eui64(value=(1,2,3,4,5,6,7,8)),
            available_index = self.available_index,
        )
        res = AVDECC_set_adpdu(self.handle, adpdu)
        logging.debug("AVDECC_set_adpdu done")
        assert res == 0

        self.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_AVAILABLE, self.entity)
        self.available_index += 1

        if self.discover:
            self.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER, 0)

        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if not issubclass(exception_type, KeyboardInterrupt):
            print("Exception:", exception_value)

        self.send_adp(av.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity)

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

    @av.AVDECC_ADP_CALLBACK
    def _adp_cb(handle, frame_ptr, adpdu_ptr):
        AVDECC.handles[handle].recv_adp(adpdu_ptr.contents)

    @av.AVDECC_ACMP_CALLBACK
    def _acmp_cb(handle, frame_ptr, acmpdu_ptr):
        AVDECC.handles[handle].recv_acmp(acmpdu_ptr.contents)

    @av.AVDECC_AECP_AEM_CALLBACK
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

    with AVDECC(intf=args.intf, valid_time=args.valid, discover=args.discover) as avdecc:

        while(True):
            time.sleep(0.1)
