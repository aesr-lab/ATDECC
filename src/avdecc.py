#!/usr/bin/env python3

import ctypes
import avdecc_api
from avdecc_api import AVDECC_create, AVDECC_destroy, AVDECC_send_adp, AVDECC_set_adpdu, AVDECC_send_acmp, AVDECC_send_aecp
import time
import logging

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


class AVDECC:
    handles = {}

    def __init__(self, intf, entity=0, debug=False, verbosity=0):
        self.intf = intf
        self.debug = debug
        self.verbosity = verbosity
        self.handle = ctypes.c_void_p()
        self.entity = entity

    def __enter__(self):
        intf = ctypes.c_char_p(self.intf.encode())
        res = AVDECC_create(ctypes.byref(self.handle), intf, AVDECC._adp_cb, AVDECC._acmp_cb, AVDECC._aecp_aem_cb)
        assert res == 0
        logging.debug("AVDECC_create done")
        AVDECC.handles[self.handle.value] = self  # register instance

        adpdu = avdecc_api.struct_jdksavdecc_adpdu(
            entity_model_id = avdecc_api.struct_jdksavdecc_eui64(value=(1,2,3,4,5,6,7,8)),
            entity_capabilities=avdecc_api.JDKSAVDECC_ADP_ENTITY_CAPABILITY_CLASS_A_SUPPORTED +
                                avdecc_api.JDKSAVDECC_ADP_ENTITY_CAPABILITY_GPTP_SUPPORTED,
            listener_stream_sinks=16,
            listener_capabilities=avdecc_api.JDKSAVDECC_ADP_LISTENER_CAPABILITY_IMPLEMENTED +
                                  avdecc_api.JDKSAVDECC_ADP_LISTENER_CAPABILITY_AUDIO_SINK,
            gptp_grandmaster_id=avdecc_api.struct_jdksavdecc_eui64(value=(1,2,3,4,5,6,7,8)),
        )
        res = AVDECC_set_adpdu(self.handle, adpdu)
        logging.debug("AVDECC_set_adpdu done")
        assert res == 0

        self.send_adp(avdecc_api.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_AVAILABLE, self.entity)

        if True:
            self.send_adp(avdecc_api.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER, 0)

        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if not issubclass(exception_type, KeyboardInterrupt):
            print("Exception:", exception_value)

        self.send_adp(avdecc_api.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DEPARTING, self.entity)

        # we need a bit of time so that the previous message can get through
        time.sleep(0.5)

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
#    parser.add_argument("--discover", action='store_true', help="Discover AVDECC entities")
    parser.add_argument('-d', "--debug", action='store_true', default=0,
                        help="Enable debug mode")
    parser.add_argument('-v', "--verbose", action='count', default=0,
                        help="Increase verbosity")
#    parser.add_argument("args", nargs='*')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    with AVDECC(intf=args.intf, entity=args.entity, verbosity=args.verbose) as avdecc:

        while(True):
            time.sleep(0.1)
