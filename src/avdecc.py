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
import netifaces
import traceback
import pdb


def hexdump(bts):
    return "".join(f"{x:02x}" for x in bts)

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

def str_to_avstr(s :str) -> av.struct_jdksavdecc_string:
    r = av.struct_jdksavdecc_string()
    r.value[:] = struct.pack("64s", s.encode('ascii'))
    return r

def pack_struct(s, byte_order='!'): #, level=''):
    """
    Pack structure with given byte-order
    TODO: this should be a class wrapper around a struct
          where the struct.pack format codes and the total length is evaluated with the class.
          The actual packing then happens on a pre-allocated array with the class instance.
    """
    r = bytes()
    for n,t in s._fields_:
        v = getattr(s, n)
        try:
            ln = t._length_
        except AttributeError:
            ln = None
            
        if ln is None:
            try:
                tp = t._type_
            except AttributeError:
                # not an atomic type, assume a struct
                tp = None
            if tp is None:
                vb = pack_struct(v, byte_order=byte_order) #, level=n+'.')
            else:
                assert type(tp) is str
#                print(level+n, t, tp)
                vb = struct.pack(byte_order+tp, v)
        else:
            # is array
            tp = t._type_._type_
#            print(level+n, t, f"{ln}{tp}")
            vb = struct.pack(f"{byte_order}{ln}{tp}", *v)

        r = r+vb
    return r


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
        api_enum('JDKSAVDECC_AEM_STATUS_', hdr.status),
        hdr.control_data_length,
        eui_to_str(hdr.target_entity_id),
    )

def aecpdu_aem_str(aecpdu_aem):
    if aecpdu_aem is None:
        logging.warning("AECP AEM: DU is none")
        return

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


def mac_to_eui48(mac):
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

    v = av.struct_jdksavdecc_eui48()
    v.value[:] = mac
    return v


def mac_to_eid(mac):
    m = mac_to_eui48(mac).value
    v = av.struct_jdksavdecc_eui64()
    v.value[:] = (m[0]^0x02, m[1], m[2], 0xff, 0xf0, m[3], m[4], m[5])
    return v


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

def jdksavdecc_eui64_set(v, base, pos: int) -> int:
    base[pos:pos+8] = v.value
    return pos+8

def jdksavdecc_uint64_set(v, base, pos: int) -> int:
    struct.pack_into('!Q', base, pos, v)
    return pos+8

def jdksavdecc_uint32_set(v, base, pos: int) -> int:
    struct.pack_into('!L', base, pos, v)
    return pos+4

def jdksavdecc_uint16_set(v, base, pos: int) -> int:
    struct.pack_into('!H', base, pos, v)
    return pos+2

def jdksavdecc_uint8_set(v, base, pos: int) -> int:
    struct.pack_into('!B', base, pos, v)
    return pos+1

def jdksavdecc_subtype_data_set_cd( v: bool, base, pos: int ):
    base[pos] = ( base[pos] & 0x7f ) | ( 0x80 if v else 0x00 )

def jdksavdecc_common_control_header_set_subtype( v, base, pos: int ):
    base[pos] = ( base[pos] & 0x80 ) | ( v & 0x7f )

def jdksavdecc_subtype_data_set_sv( v: bool, base, pos: int ):
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

def jdksavdecc_common_control_header_set_stream_id( v: av.struct_jdksavdecc_eui64, base, pos: int ):
    jdksavdecc_eui64_set( v, base, pos + av.JDKSAVDECC_COMMON_CONTROL_HEADER_OFFSET_STREAM_ID )

def jdksavdecc_adpdu_common_control_header_write( p: av.struct_jdksavdecc_adpdu_common_control_header,
                                            base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN )
    if r >= 0:
        jdksavdecc_subtype_data_set_cd( p.cd, base, pos )
        jdksavdecc_common_control_header_set_subtype( p.subtype, base, pos )
        jdksavdecc_subtype_data_set_sv( p.sv, base, pos)
        jdksavdecc_subtype_data_set_version( p.version, base, pos)
        jdksavdecc_avtp_subtype_data_set_control_data ( p.message_type, base, pos)
        jdksavdecc_subtype_data_set_status( p.valid_time, base, pos)
        jdksavdecc_subtype_data_set_control_data_length( p.control_data_length, base, pos)
        jdksavdecc_common_control_header_set_stream_id( p.entity_id, base, pos )
    return r

def jdksavdecc_aecpdu_common_control_header_write( p: av.struct_jdksavdecc_aecpdu_common_control_header,
                                                   base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN )
    if r >= 0:
        jdksavdecc_subtype_data_set_cd( p.cd, base, pos )
        jdksavdecc_common_control_header_set_subtype( p.subtype, base, pos )
        jdksavdecc_subtype_data_set_sv( p.sv, base, pos )
        jdksavdecc_subtype_data_set_version( p.version, base, pos )
        jdksavdecc_avtp_subtype_data_set_control_data( p.message_type, base, pos )
        jdksavdecc_subtype_data_set_status( p.status, base, pos )
        jdksavdecc_subtype_data_set_control_data_length( p.control_data_length, base, pos )
        jdksavdecc_common_control_header_set_stream_id( p.target_entity_id, base, pos )
    return r


def jdksavdecc_adpdu_write( p: av.struct_jdksavdecc_adpdu , 
                            base, pos: int, ln: int ) -> int:
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
                  target_entity: av.struct_jdksavdecc_eui64) -> av.struct_jdksavdecc_frame:
    adpdu.header.cd = 1
    adpdu.header.subtype = av.JDKSAVDECC_SUBTYPE_ADP
    adpdu.header.sv = 0
    adpdu.header.version = 0
    adpdu.header.message_type = message_type
    # valid_time should be given
    adpdu.header.control_data_length = av.JDKSAVDECC_ADPDU_LEN - av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    adpdu.header.entity_id = target_entity
    frame = av.struct_jdksavdecc_frame(
        ethertype = av.JDKSAVDECC_AVTP_ETHERTYPE,
        dest_address = uint64_to_eui48(av.JDKSAVDECC_MULTICAST_ADP_ACMP_MAC),
    )
    frame.length = jdksavdecc_adpdu_write( adpdu, frame.payload, 0, len(frame.payload) )
    return frame


def jdksavdecc_aecpdu_common_set_controller_entity_id( v: av.struct_jdksavdecc_eui64, base, pos: int ):
    jdksavdecc_eui64_set( v, base, pos + av.JDKSAVDECC_AECPDU_COMMON_OFFSET_CONTROLLER_ENTITY_ID )

def jdksavdecc_aecpdu_common_set_sequence_id( v: av.uint16_t , base, pos: int ):
    jdksavdecc_uint16_set( v, base, pos + av.JDKSAVDECC_AECPDU_COMMON_OFFSET_SEQUENCE_ID )

def jdksavdecc_aecpdu_common_write( p: av.struct_jdksavdecc_aecpdu_common, 
                                    base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_AECPDU_COMMON_LEN )
    if r >= 0:
        jdksavdecc_aecpdu_common_control_header_write( p.header, base, pos, ln )
        jdksavdecc_aecpdu_common_set_controller_entity_id( p.controller_entity_id, base, pos )
        jdksavdecc_aecpdu_common_set_sequence_id( p.sequence_id, base, pos )
    return r

def jdksavdecc_aecpdu_aem_set_command_type( v: av.uint16_t, base, pos: int ):
    jdksavdecc_uint16_set( v, base, pos + av.JDKSAVDECC_AECPDU_AEM_OFFSET_COMMAND_TYPE )
    return av.JDKSAVDECC_AECPDU_AEM_OFFSET_COMMAND_TYPE+2

def jdksavdecc_aecpdu_aem_write( p: av.struct_jdksavdecc_aecpdu_aem, 
                                 base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_AECPDU_AEM_LEN )
    if r >= 0:
        jdksavdecc_aecpdu_common_write( p.aecpdu_header, base, pos, ln )
        jdksavdecc_aecpdu_aem_set_command_type( p.command_type, base, pos )
    return r

def jdksavdecc_aecpdu_write( p: av.struct_jdksavdecc_aecpdu_common, 
                                 base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, av.JDKSAVDECC_AECPDU_COMMON_LEN )
    if r >= 0:
        jdksavdecc_aecpdu_common_write( p, base, pos, ln )
    return r

def aecp_form_msg( du, #av.struct_jdksavdecc_aecpdu_common or av.struct_jdksavdecc_aecpdu_aem,
#                       message_type_code: av.uint16_t ,
                       destination_mac: av.struct_jdksavdecc_eui48 = None,
#                       target_entity_id: av.struct_jdksavdecc_eui64,
#                       controller_entity_id: av.struct_jdksavdecc_eui64,
                       command_payload = None,
                     ) -> av.struct_jdksavdecc_frame:

    # copy additional command_payload
    if command_payload is None:
        command_payload = bytes()
    else:
        # convert struct to byte array
        command_payload = bytes(command_payload)

    if type(du) is av.struct_jdksavdecc_aecpdu_aem:
        aecpdu_header = du.aecpdu_header
        hdrlen = av.JDKSAVDECC_AECPDU_AEM_LEN - av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    elif type(du) is av.struct_jdksavdecc_aecpdu_common:
        aecpdu_header = du
        hdrlen = av.JDKSAVDECC_AECPDU_COMMON_LEN - av.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    else:
        raise NotImplementedError("AECP response type not implemented")
        
#    pdb.set_trace()

    aecpdu_header.header.cd = 1
    aecpdu_header.header.subtype = av.JDKSAVDECC_SUBTYPE_AECP
    aecpdu_header.header.sv = 0
    aecpdu_header.header.version = 0
    aecpdu_header.header.control_data_length = hdrlen + len(command_payload)
    
    frame = av.struct_jdksavdecc_frame(
        ethertype = av.JDKSAVDECC_AVTP_ETHERTYPE,
        dest_address = destination_mac \
                       if destination_mac is not None \
#                       else uint64_to_eui48(0x0c4de9cabdc5),
                       else uint64_to_eui48(av.JDKSAVDECC_MULTICAST_ADP_ACMP_MAC),
                       # address should be unicast!!
    )
    
    frame.length = jdksavdecc_aecpdu_write( aecpdu_header, frame.payload, 0, len( frame.payload ) )

    if type(du) is av.struct_jdksavdecc_aecpdu_aem:
        frame.length = jdksavdecc_aecpdu_aem_set_command_type( du.command_type, frame.payload, 0 )

    if len(command_payload) and frame.length + len(command_payload) < len( frame.payload ):
#        pdb.set_trace()
        frame.payload[frame.length:frame.length+len(command_payload)] = command_payload
        frame.length += len(command_payload)

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

            print("READ_DESCRIPTOR", api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type))

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
                    object_name=str_to_avstr("16 out"),
                    localized_description=0,
                    descriptor_counts_count=3,
                    descriptor_counts_offset=74,
                )
                descriptor_counts = struct.pack("!6H",
                    av.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_VIDEO_UNIT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_SENSOR_UNIT, 0,
                    av.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_JACK_INPUT, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_JACK_OUTPUT, 16,
                    av.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE, 1,
#                    av.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE, 1,
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
#                    av.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_CONTROL_BLOCK, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_TIMING, 0,
#                    av.JDKSAVDECC_DESCRIPTOR_PTP_INSTANCE, 0,
                )
                response_payload = pack_struct(descriptor)+descriptor_counts

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT:
                configuration_index = 0 # need to adjust if more than one configuration
                descriptor = av.struct_jdksavdecc_descriptor_audio_unit(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=av.struct_jdksavdecc_string(),
                    localized_description=0,
                    clock_domain_index=0,
                    number_of_stream_input_ports=1,
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
                configuration_index = 0 # need to adjust if more than one configuration
                descriptor = av.struct_jdksavdecc_descriptor_stream_port(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    clock_domain_index=0,
                    port_flags=0x0001, # CLOCK_SYNC_SOURCE - Indicates that the Port can be used as a clock synchronization source.
#                               0x0002 + # ASYNC_SAMPLE_RATE_CONV - Indicates that the Port has an asynchronous sample rate con­vertor to convert sample rates between another Clock Domain and the Unit’s.
#                               0x0004, # SYNC_SAMPLE_RATE_CONV - Indicates that the Port has a synchronous sample rate convertor to convert between sample rates in the same Clock Domain.
                    number_of_controls=0,
                    base_control=0,
                    number_of_clusters=0,
                    base_cluster=0,
                    number_of_maps=0,
                    base_map=0,
                )
                response_payload = pack_struct(descriptor)

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT:
                configuration_index = 0 # need to adjust if more than one configuration
                descriptor = av.struct_jdksavdecc_descriptor_stream(
                    descriptor_type=descriptor_type, 
                    descriptor_index=descriptor_index,
                    object_name=av.struct_jdksavdecc_string(),
                    localized_description=0,
                    clock_domain_index=0,
                    stream_flags=av.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLOCK_SYNC_SOURCE +
                                    av.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLASS_A +
                                    0x8000,  # SUPPORTS_NO_SRP - new flag 
                    current_format=uint64_to_eui64(0),
                    formats_offset=0,
                    number_of_formats=1,
                    backup_talker_entity_id_0=uint64_to_eui64(0),
                    backup_talker_unique_id_0=0,
                    backup_talker_entity_id_1=uint64_to_eui64(0),
                    backup_talker_unique_id_1=0,
                    backup_talker_entity_id_2=uint64_to_eui64(0),
                    backup_talker_unique_id_2=0,
                    backedup_talker_entity_id=uint64_to_eui64(0),
                    backedup_talker_unique=0,
                    avb_interface_index=0,
                    buffer_length=0,
                )
                formats = struct.pack("!2H",0,0)
                response_payload = pack_struct(descriptor)+formats

            elif descriptor_type == av.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE:
                configuration_index = 0 # need to adjust if more than one configuration
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
                    clock_identity=uint64_to_eui64(0),
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
                
            else:
                descriptor = None    
            
            if descriptor is not None:
                response = copy.deepcopy(command)
                response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
                response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_SUCCESS
                prefix = struct.pack("!2H", configuration_index, 0)
                response_payload = prefix+response_payload

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_COUNTERS:
            descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

            print("GET_COUNTERS: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!2HL",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                0, # counters_valid
            )+bytes(128)

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO:
            descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

            print("GET_AVB_INFO: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

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

            print("GET_AS_PATH: descriptor_index=%d"%descriptor_index)

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = av.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = av.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!2H",
                descriptor_index, # descriptor_index
                0, # count
            )

        elif command.command_type == av.JDKSAVDECC_AEM_COMMAND_GET_AUDIO_MAP:
            descriptor_type, descriptor_index, map_index, _ = struct.unpack_from("!4H", payload)

            print("GET_AUDIO_MAP: descriptor_type=%s, descriptor_index=%d"%(
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
                0, # number_of_maps
                0, # number_of_mappings
                0, # reserved
                # N * Audio_mappings_format
            )

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
