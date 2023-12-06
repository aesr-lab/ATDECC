import pytest
import yaml
from unittest.mock import patch, Mock

import atdecc_api as at
from util import *
from aem import AEMDescriptorFactory
from adp import EntityInfo

class TestAEMDescriptors:
    def config(self):
        return yaml.safe_load(open("./tests/fixtures/config.yml", 'r'))

    def test_aem_descriptor_entity(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_entity = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_ENTITY, descriptor_index, em, self.config())

        assert "aesrl 16-channel" == avstr_to_str(descriptor_entity.descriptor.entity_name)
        assert "aesrl" == avstr_to_str(descriptor_entity.descriptor.group_name)
        assert 42 == eui64_to_uint64(descriptor_entity.descriptor.entity_id)

    def test_aem_descriptor_configuration(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_configuration = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_CONFIGURATION, descriptor_index, em, self.config())

        # from config
        assert 5 == descriptor_configuration.descriptor.descriptor_counts_count

        # payload assertion
        payload = struct.unpack("!10H", descriptor_configuration.data)
        descriptor_counts = {k: v for k, v in [payload[i:i + 2] for i in range(0, len(payload), 2)]}

        assert 1 == descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT]
        assert 1 == descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT]
        assert 1 == descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE]
        assert 1 == descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE]
        assert 1 == descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN]

        # assert that non-existing descriptors raise a KeyError
        with pytest.raises(KeyError):
            _ = descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT]
            _ = descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_JACK_INPUT]
            _ = descriptor_counts[at.JDKSAVDECC_DESCRIPTOR_JACK_OUTPUT]


        # default values
        assert 0 == descriptor_configuration.descriptor.localized_description
        assert at.JDKSAVDECC_DESCRIPTOR_CONFIGURATION_OFFSET_DESCRIPTOR_COUNTS == descriptor_configuration.descriptor.descriptor_counts_offset

    def test_aem_descriptor_audio_unit(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_audio_unit = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_AUDIO_UNIT, descriptor_index, em, self.config())

        # from config
        assert "AESRL Audio Unit" == avstr_to_str(descriptor_audio_unit.descriptor.object_name)
        assert 48000 == descriptor_audio_unit.descriptor.current_sampling_rate
        assert 1 == descriptor_audio_unit.descriptor.sampling_rates_count
        assert 2 == descriptor_audio_unit.descriptor.number_of_stream_input_ports
        assert 0 == descriptor_audio_unit.descriptor.number_of_stream_output_ports
        assert 0 == descriptor_audio_unit.descriptor.number_of_external_input_ports
        assert 16 == descriptor_audio_unit.descriptor.number_of_external_output_ports
        assert 0 == descriptor_audio_unit.descriptor.number_of_internal_input_ports
        assert 0 == descriptor_audio_unit.descriptor.number_of_internal_output_ports
        assert 0 == descriptor_audio_unit.descriptor.number_of_controls
        assert 0 == descriptor_audio_unit.descriptor.number_of_signal_selectors
        assert 0 == descriptor_audio_unit.descriptor.number_of_mixers
        assert 0 == descriptor_audio_unit.descriptor.number_of_matrices
        assert 0 == descriptor_audio_unit.descriptor.number_of_splitters
        assert 0 == descriptor_audio_unit.descriptor.number_of_combiners
        assert 0 == descriptor_audio_unit.descriptor.number_of_demultiplexers
        assert 0 == descriptor_audio_unit.descriptor.number_of_multiplexers
        assert 0 == descriptor_audio_unit.descriptor.number_of_transcoders
        assert 0 == descriptor_audio_unit.descriptor.number_of_control_blocks

        # default values
        assert 0 == descriptor_audio_unit.descriptor.localized_description
        assert 0 == descriptor_audio_unit.descriptor.clock_domain_index
        assert 0 == descriptor_audio_unit.descriptor.base_stream_input_port
        assert 0 == descriptor_audio_unit.descriptor.base_stream_output_port
        assert 0 == descriptor_audio_unit.descriptor.base_external_input_port
        assert 0 == descriptor_audio_unit.descriptor.base_external_output_port
        assert 0 == descriptor_audio_unit.descriptor.base_internal_input_port
        assert 0 == descriptor_audio_unit.descriptor.base_internal_output_port
        assert 0 == descriptor_audio_unit.descriptor.base_control
        assert 0 == descriptor_audio_unit.descriptor.base_signal_selector
        assert 0 == descriptor_audio_unit.descriptor.base_mixer
        assert 0 == descriptor_audio_unit.descriptor.base_matrix
        assert 0 == descriptor_audio_unit.descriptor.base_splitter
        assert 0 == descriptor_audio_unit.descriptor.base_combiner
        assert 0 == descriptor_audio_unit.descriptor.base_demultiplexer
        assert 0 == descriptor_audio_unit.descriptor.base_multiplexer
        assert 0 == descriptor_audio_unit.descriptor.base_transcoder
        assert 0 == descriptor_audio_unit.descriptor.base_control_block

    def test_aem_descriptor_stream_input(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_stream_input = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT, descriptor_index, em, self.config())
        # from config
        assert 0x0205022002006000 == eui64_to_uint64(descriptor_stream_input.descriptor.current_format)
        assert 666 == descriptor_stream_input.descriptor.buffer_length
        assert at.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLOCK_SYNC_SOURCE + at.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLASS_A + 0x8000 == descriptor_stream_input.descriptor.stream_flags

        # default values
        assert "Audio Input Stream 1" == avstr_to_str(descriptor_stream_input.descriptor.object_name)
        assert 0 == descriptor_stream_input.descriptor.clock_domain_index
        assert 0 == descriptor_stream_input.descriptor.avb_interface_index
        assert 138 == descriptor_stream_input.descriptor.formats_offset
        assert 0 == eui64_to_uint64(descriptor_stream_input.descriptor.backup_talker_entity_id_0)
        assert 0 == descriptor_stream_input.descriptor.backup_talker_unique_id_0
        assert 0 == eui64_to_uint64(descriptor_stream_input.descriptor.backup_talker_entity_id_1)
        assert 0 == descriptor_stream_input.descriptor.backup_talker_unique_id_1
        assert 0 == eui64_to_uint64(descriptor_stream_input.descriptor.backup_talker_entity_id_2)
        assert 0 == descriptor_stream_input.descriptor.backup_talker_unique_id_2
        assert 0 == eui64_to_uint64(descriptor_stream_input.descriptor.backedup_talker_entity_id)
        assert 0 == descriptor_stream_input.descriptor.backedup_talker_unique

    def test_aem_descriptor_stream_output(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_stream_output = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT, descriptor_index, em, self.config())
        # from config
        assert 0x0205022002006000 == eui64_to_uint64(descriptor_stream_output.descriptor.current_format)
        assert 666 == descriptor_stream_output.descriptor.buffer_length
        assert at.JDKSAVDECC_DESCRIPTOR_STREAM_FLAG_CLASS_A + 0x8000 == descriptor_stream_output.descriptor.stream_flags

        # default values
        assert "Audio Output Stream 1" == avstr_to_str(descriptor_stream_output.descriptor.object_name)
        assert 0 == descriptor_stream_output.descriptor.clock_domain_index
        assert 0 == descriptor_stream_output.descriptor.avb_interface_index
        assert 138 == descriptor_stream_output.descriptor.formats_offset
        assert 0 == eui64_to_uint64(descriptor_stream_output.descriptor.backup_talker_entity_id_0)
        assert 0 == descriptor_stream_output.descriptor.backup_talker_unique_id_0
        assert 0 == eui64_to_uint64(descriptor_stream_output.descriptor.backup_talker_entity_id_1)
        assert 0 == descriptor_stream_output.descriptor.backup_talker_unique_id_1
        assert 0 == eui64_to_uint64(descriptor_stream_output.descriptor.backup_talker_entity_id_2)
        assert 0 == descriptor_stream_output.descriptor.backup_talker_unique_id_2
        assert 0 == eui64_to_uint64(descriptor_stream_output.descriptor.backedup_talker_entity_id)
        assert 0 == descriptor_stream_output.descriptor.backedup_talker_unique

    def test_aem_descriptor_jack_input(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_jack_input = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_JACK_INPUT, descriptor_index, em, self.config())

        # default values
        assert 0 == descriptor_jack_input.descriptor.jack_flags
        assert at.JDKSAVDECC_JACK_TYPE_BALANCED_ANALOG == descriptor_jack_input.descriptor.jack_type
        assert 0 == descriptor_jack_input.descriptor.number_of_controls
        assert 0 == descriptor_jack_input.descriptor.base_control

        # from config
        assert "Audio In Jack 1" == avstr_to_str(descriptor_jack_input.descriptor.object_name)

    def test_aem_descriptor_jack_output(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_jack_output = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_JACK_OUTPUT, descriptor_index, em, self.config())

        # default values
        assert 0 == descriptor_jack_output.descriptor.jack_flags
        assert 0 == descriptor_jack_output.descriptor.number_of_controls
        assert 0 == descriptor_jack_output.descriptor.base_control

        # from config
        assert at.JDKSAVDECC_JACK_TYPE_DIGITAL == descriptor_jack_output.descriptor.jack_type
        assert "Audio Out Jack 1" == avstr_to_str(descriptor_jack_output.descriptor.object_name)

    def test_aem_descriptor_avb_interface(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_avb_interface = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE, descriptor_index, em, self.config())

        # default
        assert em.entity_id == eui64_to_uint64(descriptor_avb_interface.descriptor.clock_identity)
        assert 0 == descriptor_avb_interface.descriptor.priority1
        assert 0 == descriptor_avb_interface.descriptor.clock_class
        assert 0 == descriptor_avb_interface.descriptor.offset_scaled_log_variance
        assert 0 == descriptor_avb_interface.descriptor.clock_accuracy
        assert 0 == descriptor_avb_interface.descriptor.priority2
        assert 0 == descriptor_avb_interface.descriptor.domain_number
        assert 0 == descriptor_avb_interface.descriptor.log_sync_interval
        assert 0 == descriptor_avb_interface.descriptor.log_announce_interval
        assert 0 == descriptor_avb_interface.descriptor.log_pdelay_interval
        assert 0 == descriptor_avb_interface.descriptor.port_number

        # from config
        assert "AESRL AVB Interface" == avstr_to_str(descriptor_avb_interface.descriptor.object_name)
        assert 0xb0d5ccfc4d94 == eui48_to_uint64(descriptor_avb_interface.descriptor.mac_address)
        assert at.JDKSAVDECC_AVB_INTERFACE_FLAG_GPTP_SUPPORTED == descriptor_avb_interface.descriptor.interface_flags

    def test_aem_descriptor_clock_source(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_clock_source = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_CLOCK_SOURCE, descriptor_index, em, self.config())

        # default
        assert 0 == descriptor_clock_source.descriptor.clock_source_location_index
        assert 0xffffffffffffffff == eui64_to_uint64(descriptor_clock_source.descriptor.clock_source_identifier)
        assert at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN == descriptor_clock_source.descriptor.clock_source_location_type
        
        # from_config
        assert 0x0002 == descriptor_clock_source.descriptor.clock_source_type
        assert 0x0001 == descriptor_clock_source.descriptor.clock_source_flags

    def test_aem_descriptor_stream_port_input(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_stream_port_input = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_INPUT, descriptor_index, em, self.config())

        # default
        assert 0 == descriptor_stream_port_input.descriptor.clock_domain_index
        assert 0 == descriptor_stream_port_input.descriptor.number_of_controls
        assert descriptor_index == descriptor_stream_port_input.descriptor.base_cluster
        assert descriptor_index == descriptor_stream_port_input.descriptor.base_map

        # from config
        assert 1 == descriptor_stream_port_input.descriptor.number_of_clusters
        assert 1 == descriptor_stream_port_input.descriptor.number_of_maps
        assert 0x0001 == descriptor_stream_port_input.descriptor.port_flags

    def test_aem_descriptor_stream_port_output(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_stream_port_output = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_STREAM_PORT_OUTPUT, descriptor_index, em, self.config())

        # default
        assert 0 == descriptor_stream_port_output.descriptor.clock_domain_index
        assert 0 == descriptor_stream_port_output.descriptor.number_of_controls
        assert descriptor_index == descriptor_stream_port_output.descriptor.base_cluster
        assert descriptor_index == descriptor_stream_port_output.descriptor.base_map
        assert 0x0000 == descriptor_stream_port_output.descriptor.port_flags

        # from config
        assert 1 == descriptor_stream_port_output.descriptor.number_of_clusters
        assert 1 == descriptor_stream_port_output.descriptor.number_of_maps


    def test_aem_descriptor_audio_cluster(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_audio_cluster = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_AUDIO_CLUSTER, descriptor_index, em, self.config())

        # from config
        assert at.JDKSAVDECC_DESCRIPTOR_INVALID == descriptor_audio_cluster.descriptor.signal_type
        assert 0 == descriptor_audio_cluster.descriptor.signal_index
        assert 8 == descriptor_audio_cluster.descriptor.channel_count
        assert "Channels 1-8" == avstr_to_str(descriptor_audio_cluster.descriptor.object_name)
        

        # default values
        assert 0 == descriptor_audio_cluster.descriptor.signal_output
        assert 0 == descriptor_audio_cluster.descriptor.path_latency
        assert 0 == descriptor_audio_cluster.descriptor.block_latency
        assert at.JDKSAVDECC_AUDIO_CLUSTER_FORMAT_MBLA == descriptor_audio_cluster.descriptor.format

    def test_aem_descriptor_audio_map(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_audio_map = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_AUDIO_MAP, descriptor_index, em, self.config())

        # from config
        assert 8 == descriptor_audio_map.descriptor.number_of_mappings

        # default values
        assert at.JDKSAVDECC_DESCRIPTOR_AUDIO_MAP_OFFSET_MAPPINGS == descriptor_audio_map.descriptor.mappings_offset

    def test_aem_descriptor_clock_domain(self):
        em = EntityInfo(entity_id=42)

        descriptor_index = 0
        descriptor_clock_domain = AEMDescriptorFactory.create_descriptor(at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN, descriptor_index, em, self.config())

        # defaults
        assert 0 == descriptor_clock_domain.descriptor.clock_source_index
        assert at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN_OFFSET_CLOCK_SOURCES == descriptor_clock_domain.descriptor.clock_sources_offset
        assert 1 == descriptor_clock_domain.descriptor.clock_sources_count
