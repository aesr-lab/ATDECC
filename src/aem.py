import atdecc_api as at
import struct

from util import *
from pdu import *


class AEM:
    pass
    
    
class AEMCommand:
    pass
    
    
class AEMDescriptor:
    def __init__(self):
        self.data = bytes()
        
    def encode(self):
        return pack_struct(self.descriptor)+self.data


class AEMDescriptor_ENTITY(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_ENTITY
    descriptor_struct = at.struct_jdksavdecc_descriptor_entity
    
    def __init__(self, 
        entity_id,
        entity_model_id,
        entity_capabilities=0,
        talker_stream_sources=0,
        talker_capabilities=0,
        listener_stream_sinks=0,
        listener_capabilities=0,
        controller_capabilities=0,
        available_index=0,
        association_id=0,
        entity_name=None,
        vendor_name_string=0,
        model_name_string=0,
        firmware_version=None,
        group_name=None,
        serial_number=None,
        configurations_count=1,
        current_configuration=0,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            entity_id=uint64_to_eui64(entity_id),
            entity_model_id=uint64_to_eui64(entity_model_id),
            entity_capabilities=entity_capabilities,
            talker_stream_sources=talker_stream_sources,
            talker_capabilities=talker_capabilities,
            listener_stream_sinks=listener_stream_sinks,
            listener_capabilities=listener_capabilities,
            controller_capabilities=controller_capabilities,
            available_index=available_index,
            association_id=association_id,
            entity_name=str_to_avstr(entity_name),
            vendor_name_string=0,
            model_name_string=0,
            firmware_version=str_to_avstr(firmware_version),
            group_name=str_to_avstr(group_name),
            serial_number=str_to_avstr(serial_number),
            configurations_count=configurations_count,
            current_configuration=current_configuration,
        )


class AEMDescriptor_CONFIGURATION(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_CONFIGURATION
    descriptor_struct = at.struct_jdksavdecc_descriptor_configuration
    
    def __init__(self, 
        descriptor_index=0,
        object_name=None,
        descriptor_counts={}
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            descriptor_counts_offset=at.JDKSAVDECC_DESCRIPTOR_CONFIGURATION_OFFSET_DESCRIPTOR_COUNTS,
            descriptor_counts_count=len(descriptor_counts),
        )
        self.data = struct.pack(
            "!%dH"%(len(descriptor_counts)*2),
            *flatten_list(descriptor_counts.items())
        )


class AEMDescriptor_AUDIO_UNIT(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT
    descriptor_struct = at.struct_jdksavdecc_descriptor_audio_unit
    
    def __init__(self, 
        descriptor_index=0,
        object_name=None,
        sampling_rates=(48000,),
        clock_domain_index=0,
        number_of_stream_input_ports=0,
        base_stream_input_port=0,
        number_of_stream_output_ports=0,
        base_stream_output_port=0,
        number_of_external_input_ports=0,
        base_external_input_port=0,
        number_of_external_output_ports=0,
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
        base_control_block=0,
        number_of_control_blocks=0,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            clock_domain_index=clock_domain_index,
            number_of_stream_input_ports=number_of_stream_input_ports,
            base_stream_input_port=base_stream_input_port,
            number_of_stream_output_ports=number_of_stream_output_ports,
            base_stream_output_port=base_stream_output_port,
            number_of_external_input_ports=number_of_external_input_ports,
            base_external_input_port=base_external_input_port,
            number_of_external_output_ports=number_of_external_output_ports,
            base_external_output_port=base_external_output_port,
            number_of_internal_input_ports=number_of_internal_input_ports,
            base_internal_input_port=base_internal_input_port,
            number_of_internal_output_ports=number_of_internal_output_ports,
            base_internal_output_port=base_internal_output_port,
            number_of_controls=number_of_controls,
            base_control=base_control,
            number_of_signal_selectors=number_of_signal_selectors,
            base_signal_selector=base_signal_selector,
            number_of_mixers=number_of_mixers,
            base_mixer=base_mixer,
            number_of_matrices=number_of_matrices,
            base_matrix=base_matrix,
            number_of_splitters=number_of_splitters,
            base_splitter=base_splitter,
            number_of_combiners=number_of_combiners,
            base_combiner=base_combiner,
            number_of_demultiplexers=number_of_demultiplexers,
            base_demultiplexer=base_demultiplexer,
            number_of_multiplexers=number_of_multiplexers,
            base_multiplexer=base_multiplexer,
            number_of_transcoders=number_of_transcoders,
            base_transcoder=base_transcoder,
            number_of_control_blocks=number_of_control_blocks,
            base_control_block=base_control_block,
            current_sampling_rate=sampling_rates[0],
            sampling_rates_offset=144,
            sampling_rates_count=len(sampling_rates),
        )
        self.data = struct.pack(
            "!%dL"%len(sampling_rates), 
            *sampling_rates  # the 3 MSBs are used for a multiplier: 000 here, means multiplier 1.
        )


class AEMDescriptor_AVB_INTERFACE(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE
    descriptor_struct = at.struct_jdksavdecc_descriptor_avb_interface
    
    def __init__(self, 
                 mac_address,
                 descriptor_index=0,
                 object_name=None,
                 interface_flags=0,
                 clock_identity=0,
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
                ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            mac_address=mac_address,
            interface_flags=interface_flags,
            clock_identity=uint64_to_eui64(clock_identity),
            priority1=priority1,
            clock_class=clock_class,
            offset_scaled_log_variance=offset_scaled_log_variance,
            clock_accuracy=clock_accuracy,
            priority2=priority2,
            domain_number=domain_number,
            log_sync_interval=log_sync_interval,
            log_announce_interval=log_announce_interval,
            log_pdelay_interval=log_pdelay_interval,
            port_number=port_number,
            # IEEE Std 1722.1TM­2021 has two more members:
            # number_of_controls (uint16)
            # base_control (uint16)
        )


class _AEMDescriptor_STREAM_PORT(AEMDescriptor):
    descriptor_struct = at.struct_jdksavdecc_descriptor_stream_port

    # doesn't exist in JDKSAVDECC
    PORT_FLAG_CLOCK_SYNC_SOURCE = 0x0001
    PORT_FLAG_ASYNC_SAMPLE_RATE_CONV = 0x0002
    PORT_FLAG_SYNC_SAMPLE_RATE_CONV = 0x0004
    
    def __init__(self, 
        descriptor_index=0,
        clock_domain_index=0,
        port_flags=0,
        number_of_controls=0,
        base_control=0,
        number_of_clusters=0,
        base_cluster=0,
        number_of_maps=0,
        base_map=0,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            clock_domain_index=clock_domain_index,
            port_flags=port_flags,
            number_of_controls=number_of_controls,
            base_control=base_control,
            number_of_clusters=number_of_clusters,
            base_cluster=base_cluster,
            number_of_maps=number_of_maps,
            base_map=base_map,
        )


class AEMDescriptor_STREAM_PORT_INPUT(_AEMDescriptor_STREAM_PORT):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_INPUT
    
    def __init__(self, *args, **kwds):
        super(AEMDescriptor_STREAM_PORT_INPUT, self).__init__(*args, **kwds)


class AEMDescriptor_STREAM_PORT_OUTPUT(_AEMDescriptor_STREAM_PORT):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_OUTPUT
    
    def __init__(self, *args, **kwds):
        super(AEMDescriptor_STREAM_PORT_OUTPUT, self).__init__(*args, **kwds)


class _AEMDescriptor_STREAM(AEMDescriptor):
    descriptor_struct = at.struct_jdksavdecc_descriptor_stream
    
    STREAM_FLAG_SUPPORTS_NO_SRP = 0x8000
    
    def __init__(self, 
        descriptor_index=0,
        object_name=None,
        clock_domain_index=0,
        stream_flags=0,
        stream_formats=(0x0205022002006000,),  # Standard/HC32 (48kHz, 32-bit int, 8 ch per frame, 6 smps per frame)
        avb_interface_index=0,
        buffer_length=0,
        timing=0,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            clock_domain_index=clock_domain_index,
            stream_flags=stream_flags, 
            current_format=uint64_to_eui64(stream_formats[0]),
            formats_offset=at.JDKSAVDECC_DESCRIPTOR_STREAM_OFFSET_FORMATS+3*2,
            number_of_formats=len(stream_formats), # N
            backup_talker_entity_id_0=uint64_to_eui64(0),
            backup_talker_unique_id_0=0,
            backup_talker_entity_id_1=uint64_to_eui64(0),
            backup_talker_unique_id_1=0,
            backup_talker_entity_id_2=uint64_to_eui64(0),
            backup_talker_unique_id_2=0,
            backedup_talker_entity_id=uint64_to_eui64(0),
            backedup_talker_unique=0,
            avb_interface_index=avb_interface_index,
            buffer_length=buffer_length,
        )
        self.data = struct.pack("!3H%dQ"%len(stream_formats),
            self.descriptor.formats_offset+8*self.descriptor.number_of_formats, # redundant_offset (138 + 8*N)
            0, # number_of_redundant_streams R
            timing, # timing
            # N stream formats
            *stream_formats,
            # R redundant streams
        )


class AEMDescriptor_STREAM_INPUT(_AEMDescriptor_STREAM):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT
    
    def __init__(self, *args, **kwds):
        super(AEMDescriptor_STREAM_INPUT, self).__init__(*args, **kwds)


class AEMDescriptor_STREAM_OUTPUT(_AEMDescriptor_STREAM):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT
    
    def __init__(self, *args, **kwds):
        super(AEMDescriptor_STREAM_OUTPUT, self).__init__(*args, **kwds)


class AEMDescriptor_AUDIO_CLUSTER(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_AUDIO_CLUSTER
    descriptor_struct = at.struct_jdksavdecc_descriptor_audio_cluster
    
    def __init__(self, 
        signal_type,  # e.g. at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_INPUT or at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_OUTPUT
        signal_index=0,
        descriptor_index=0,
        object_name=None,
        signal_output=0,
        path_latency=0,
        block_latency=0,
        channel_count=1,
        format=at.JDKSAVDECC_AUDIO_CLUSTER_FORMAT_MBLA,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            signal_type=signal_type,  # The descriptor_type for the signal source of the cluster.
            signal_index=signal_index,  # The descriptor_index for the signal source of the cluster.
            signal_output=signal_output,
            path_latency=path_latency,
            block_latency=block_latency,
            channel_count=channel_count,
            format=format,
        )


class AEMDescriptor_AUDIO_MAP(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_AUDIO_MAP
    descriptor_struct = at.struct_jdksavdecc_descriptor_audio_map
    
    def __init__(self, 
        descriptor_index=0,
        mappings=(),  # 4-tuple mappings
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            mappings_offset=at.JDKSAVDECC_DESCRIPTOR_AUDIO_MAP_OFFSET_MAPPINGS,
            number_of_mappings=len(mappings), # N
            # N mappings: !4H = (mapping_stream_index, mapping_stream_channel, mapping_cluster_offset, mapping_cluster_channel)
        )
        self.data = struct.pack("!%dH"%(len(mappings)*4), *mappings)


class AEMDescriptor_CLOCK_DOMAIN(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN
    descriptor_struct = at.struct_jdksavdecc_descriptor_clock_domain
    
    def __init__(self, 
        descriptor_index=0,
        object_name=None,
        clock_sources=(),
        clock_source_index=0,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            clock_source_index=clock_source_index,
            clock_sources_offset=at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN_OFFSET_CLOCK_SOURCES,
            clock_sources_count=len(clock_sources), # C
            # C*2: list of CLOCK_SOURCE descriptor indices
        )
        self.data = struct.pack("!%dH"%len(clock_sources), *clock_sources)
                
                
class AEMDescriptor_CLOCK_SOURCE(AEMDescriptor):
    descriptor_type = at.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE
    descriptor_struct = at.struct_jdksavdecc_descriptor_clock_source
    
    CLOCK_SOURCE_FLAGS_STREAM_ID = 0x0001
    CLOCK_SOURCE_FLAGS_LOCAL_ID = 0x0002
    
    CLOCK_SOURCE_TYPE_INTERNAL = 0x0000
    CLOCK_SOURCE_TYPE_EXTERNAL = 0x0001
    CLOCK_SOURCE_TYPE_INPUT_STREAM = 0x0002
    CLOCK_SOURCE_TYPE_EXPANSION = 0xffff
    
    def __init__(self, 
        descriptor_index=0,
        object_name=None,
        clock_source_flags=CLOCK_SOURCE_FLAGS_LOCAL_ID,
        clock_source_type=CLOCK_SOURCE_TYPE_INTERNAL,
        clock_source_identifier=0xffffffffffffffff,
        clock_source_location_type=at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN,
        clock_source_location_index=0,
    ):
        self.descriptor = self.descriptor_struct(
            descriptor_type=self.descriptor_type, 
            descriptor_index=descriptor_index,
            object_name=str_to_avstr(object_name),
            localized_description=0,
            clock_source_flags=clock_source_flags,
            clock_source_type=clock_source_type,
            clock_source_identifier=uint64_to_eui64(clock_source_identifier),
            clock_source_location_type=clock_source_location_type,
            clock_source_location_index=clock_source_location_index,
        )
