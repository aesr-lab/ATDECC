import ctypes

from .. import atdecc_api as at

class struct_acmp_listener_stream_info(at.Structure):
    pass

struct_acmp_listener_stream_info._fields_ = [
    ('talker_entity_id', at.struct_jdksavdecc_eui64),
    ('talker_unique_id', ctypes.c_uint16),
    ('connected', ctypes.c_bool),
    ('stream_id', at.struct_jdksavdecc_eui64),
    ('stream_dest_mac', at.struct_jdksavdecc_eui48),
    ('controller_entity_id', at.struct_jdksavdecc_eui64),
    ('flags', ctypes.c_uint16),
    ('stream_vlan_id', ctypes.c_uint16),
    ('pending_connection', ctypes.c_bool),
]

class struct_acmp_inflight_command(at.Structure):
    pass

struct_acmp_inflight_command._fields_ = [
    ('timeout', ctypes.c_uint16),
    ('retried', ctypes.c_bool),
    ('command', at.struct_jdksavdecc_acmpdu),
    ('original_sequence_id', ctypes.c_uint16),
]
