from .util import *

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
