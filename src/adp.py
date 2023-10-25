from pdu import *
from pdu_print import *
from aem import *

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
