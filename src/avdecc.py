#!/usr/bin/env python3

import ctypes
import avdecc_api
from avdecc_api import AVDECC_create, AVDECC_destroy, AVDECC_send_adp, AVDECC_send_acmp, AVDECC_send_aecp
import time

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

@avdecc_api.AVDECC_ADP_CALLBACK
def adp_cb(frame_ptr, adpdu_ptr):
    adpdu = adpdu_ptr.contents
    print("ADP:", adpdu_str(adpdu))

@avdecc_api.AVDECC_ACMP_CALLBACK
def acmp_cb(frame_ptr, acmpdu_ptr):
    acmpdu = acmpdu_ptr.content
    print("ACMP", acmpdu)

@avdecc_api.AVDECC_AECP_AEM_CALLBACK
def aecp_aem_cb(frame_ptr, aecpdu_aem_ptr):
    aecpdu_aem = aecpdu_aem_ptr.content
    print("AECP_AEM", aecpdu_aem)

def chk_err(res):
    if res:
        raise RuntimeError("Error", res)

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-i", "--intf", type=str, default='eth0',
                        help="Network interface (default='%(default)s')")
    parser.add_argument('-d', "--debug", action='store_true', default=0,
                        help="Enable debug mode")
    parser.add_argument('-v', "--verbose", action='count', default=0,
                        help="Increase verbosity")
    parser.add_argument("args", nargs='*')
    args = parser.parse_args()

    try:
        handle = ctypes.c_void_p()
        intf = ctypes.c_char_p(args.intf.encode())
        res = AVDECC_create(ctypes.byref(handle), intf, adp_cb, acmp_cb, aecp_aem_cb)
        assert res == 0
        assert handle

        msg = ctypes.c_char_p("ENTITY_AVAILABLE".encode())
        entity = ctypes.c_char_p(args.args[0].encode())
        res = AVDECC_send_adp(handle, msg, entity)
        assert res == 0

        msg = ctypes.c_char_p("ENTITY_DISCOVER".encode())
        entity = ctypes.c_char_p(None)
        res = AVDECC_send_adp(handle, msg, entity)
        assert res == 0

        while(True):
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
        
    finally:
        msg = ctypes.c_char_p("ENTITY_DEPARTING".encode())
        entity = ctypes.c_char_p(args.args[0].encode())
        res = AVDECC_send_adp(handle, msg, entity)
        assert res == 0

        res = AVDECC_destroy(handle)
