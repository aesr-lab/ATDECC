from .util import *

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

def jdksavdecc_common_control_header_set_stream_id( v: at.struct_jdksavdecc_eui64, base, pos: int ):
    jdksavdecc_eui64_set( v, base, pos + at.JDKSAVDECC_COMMON_CONTROL_HEADER_OFFSET_STREAM_ID )

def jdksavdecc_adpdu_common_control_header_write( p: at.struct_jdksavdecc_adpdu_common_control_header,
                                            base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, at.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN )
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

def jdksavdecc_aecpdu_common_control_header_write( p: at.struct_jdksavdecc_aecpdu_common_control_header,
                                                   base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, at.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN )
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


def jdksavdecc_adpdu_write( p: at.struct_jdksavdecc_adpdu , 
                            base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, at.JDKSAVDECC_ADPDU_LEN )
    if r >= 0:
        jdksavdecc_adpdu_common_control_header_write( p.header, base, pos, ln )
        jdksavdecc_eui64_set( p.entity_model_id, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_ENTITY_MODEL_ID )
        jdksavdecc_uint32_set( p.entity_capabilities, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_ENTITY_CAPABILITIES )
        jdksavdecc_uint16_set( p.talker_stream_sources, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_TALKER_STREAM_SOURCES )
        jdksavdecc_uint16_set( p.talker_capabilities, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_TALKER_CAPABILITIES )
        jdksavdecc_uint16_set( p.listener_stream_sinks, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_LISTENER_STREAM_SINKS )
        jdksavdecc_uint16_set( p.listener_capabilities, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_LISTENER_CAPABILITIES )
        jdksavdecc_uint32_set( p.controller_capabilities, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_CONTROLLER_CAPABILITIES )
        jdksavdecc_uint32_set( p.available_index, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_AVAILABLE_INDEX )
        jdksavdecc_eui64_set( p.gptp_grandmaster_id, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_GPTP_GRANDMASTER_ID )
        jdksavdecc_uint8_set( p.gptp_domain_number, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_GPTP_DOMAIN_NUMBER )
        jdksavdecc_uint8_set( p.reserved0, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_RESERVED0 )
        jdksavdecc_uint16_set( p.identify_control_index, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_IDENTIFY_CONTROL_INDEX )
        jdksavdecc_uint16_set( p.interface_index, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_INTERFACE_INDEX )
        jdksavdecc_eui64_set( p.association_id, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_ASSOCIATION_ID )
        jdksavdecc_uint32_set( p.reserved1, base, pos + at.JDKSAVDECC_ADPDU_OFFSET_RESERVED1 )
    return r


def adp_form_msg( adpdu: at.struct_jdksavdecc_adpdu,
                  message_type: at.uint16_t,
                  target_entity: at.struct_jdksavdecc_eui64) -> at.struct_jdksavdecc_frame:
    adpdu.header.cd = 1
    adpdu.header.subtype = at.JDKSAVDECC_SUBTYPE_ADP
    adpdu.header.sv = 0
    adpdu.header.version = 0
    adpdu.header.message_type = message_type
    # valid_time should be given
    adpdu.header.control_data_length = at.JDKSAVDECC_ADPDU_LEN - at.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    adpdu.header.entity_id = target_entity
    frame = at.struct_jdksavdecc_frame(
        ethertype = at.JDKSAVDECC_AVTP_ETHERTYPE,
        dest_address = uint64_to_eui48(at.JDKSAVDECC_MULTICAST_ADP_ACMP_MAC),
    )
    frame.length = jdksavdecc_adpdu_write( adpdu, frame.payload, 0, len(frame.payload) )
    return frame


def jdksavdecc_aecpdu_common_set_controller_entity_id( v: at.struct_jdksavdecc_eui64, base, pos: int ):
    jdksavdecc_eui64_set( v, base, pos + at.JDKSAVDECC_AECPDU_COMMON_OFFSET_CONTROLLER_ENTITY_ID )

def jdksavdecc_aecpdu_common_set_sequence_id( v: at.uint16_t , base, pos: int ):
    jdksavdecc_uint16_set( v, base, pos + at.JDKSAVDECC_AECPDU_COMMON_OFFSET_SEQUENCE_ID )

def jdksavdecc_aecpdu_common_write( p: at.struct_jdksavdecc_aecpdu_common, 
                                    base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, at.JDKSAVDECC_AECPDU_COMMON_LEN )
    if r >= 0:
        jdksavdecc_aecpdu_common_control_header_write( p.header, base, pos, ln )
        jdksavdecc_aecpdu_common_set_controller_entity_id( p.controller_entity_id, base, pos )
        jdksavdecc_aecpdu_common_set_sequence_id( p.sequence_id, base, pos )
    return r

def jdksavdecc_aecpdu_aem_set_command_type( v: at.uint16_t, base, pos: int ):
    jdksavdecc_uint16_set( v, base, pos + at.JDKSAVDECC_AECPDU_AEM_OFFSET_COMMAND_TYPE )
    return at.JDKSAVDECC_AECPDU_AEM_OFFSET_COMMAND_TYPE+2

def jdksavdecc_aecpdu_aem_write( p: at.struct_jdksavdecc_aecpdu_aem, 
                                 base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, at.JDKSAVDECC_AECPDU_AEM_LEN )
    if r >= 0:
        jdksavdecc_aecpdu_common_write( p.aecpdu_header, base, pos, ln )
        jdksavdecc_aecpdu_aem_set_command_type( p.command_type, base, pos )
    return r

def jdksavdecc_aecpdu_write( p: at.struct_jdksavdecc_aecpdu_common, 
                                 base, pos: int, ln: int ) -> int:
    r = jdksavdecc_validate_range( pos, ln, at.JDKSAVDECC_AECPDU_COMMON_LEN )
    if r >= 0:
        jdksavdecc_aecpdu_common_write( p, base, pos, ln )
    return r

def aecp_form_msg( du, #at.struct_jdksavdecc_aecpdu_common or at.struct_jdksavdecc_aecpdu_aem,
#                       message_type_code: at.uint16_t ,
                       destination_mac: at.struct_jdksavdecc_eui48 = None,
#                       target_entity_id: at.struct_jdksavdecc_eui64,
#                       controller_entity_id: at.struct_jdksavdecc_eui64,
                       command_payload = None,
                     ) -> at.struct_jdksavdecc_frame:

    # copy additional command_payload
    if command_payload is None:
        command_payload = bytes()
    else:
        # convert struct to byte array
        command_payload = bytes(command_payload)

    if type(du) is at.struct_jdksavdecc_aecpdu_aem:
        aecpdu_header = du.aecpdu_header
        hdrlen = at.JDKSAVDECC_AECPDU_AEM_LEN - at.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    elif type(du) is at.struct_jdksavdecc_aecpdu_common:
        aecpdu_header = du
        hdrlen = at.JDKSAVDECC_AECPDU_COMMON_LEN - at.JDKSAVDECC_COMMON_CONTROL_HEADER_LEN
    else:
        raise NotImplementedError("AECP response type not implemented")
        
#    pdb.set_trace()

    aecpdu_header.header.cd = 1
    aecpdu_header.header.subtype = at.JDKSAVDECC_SUBTYPE_AECP
    aecpdu_header.header.sv = 0
    aecpdu_header.header.version = 0
    aecpdu_header.header.control_data_length = hdrlen + len(command_payload)
    
    frame = at.struct_jdksavdecc_frame(
        ethertype = at.JDKSAVDECC_AVTP_ETHERTYPE,
        dest_address = destination_mac \
                       if destination_mac is not None \
#                       else uint64_to_eui48(0x0c4de9cabdc5),
                       else uint64_to_eui48(at.JDKSAVDECC_MULTICAST_ADP_ACMP_MAC),
                       # address should be unicast!!
    )
    
    frame.length = jdksavdecc_aecpdu_write( aecpdu_header, frame.payload, 0, len( frame.payload ) )

    if type(du) is at.struct_jdksavdecc_aecpdu_aem:
        frame.length = jdksavdecc_aecpdu_aem_set_command_type( du.command_type, frame.payload, 0 )

    if len(command_payload) and frame.length + len(command_payload) < len( frame.payload ):
#        pdb.set_trace()
        frame.payload[frame.length:frame.length+len(command_payload)] = command_payload
        frame.length += len(command_payload)

    return frame
