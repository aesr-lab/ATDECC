#!/usr/bin/env python3

import ctypes
import avdecc_api
from avdecc_api import AVDECC_create, AVDECC_destroy, AVDECC_send_adp, AVDECC_send_acmp, AVDECC_send_aecp
import time

@avdecc_api.AVDECC_ADP_CALLBACK
def adp_cb(frame_ptr, adpdu_ptr):
    adpdu = adpdu_ptr.content
    print("ADP", adpdu)

@avdecc_api.AVDECC_ACMP_CALLBACK
def acmp_cb(frame_ptr, acmpdu_ptr):
    acmpdu = acmpdu_ptr.content
    print("ACMP", acmpdu)

@avdecc_api.AVDECC_AECP_AEM_CALLBACK
def aecp_aem_cb(frame_ptr, aecpdu_aem_ptr):
    aecpdu_aem = aecpdu_aem_ptr.content
    print("AECP_AEM", aecpdu_aem)


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-i", "--intf", type=str, default='eth0',
                        help="Network interface (default='%(default)s')")
    parser.add_argument('-d', "--debug", action='store_true', default=0,
                        help="Enable debug mode")
    parser.add_argument('-v', "--verbose", action='count', default=0,
                        help="Increase verbosity")
    args = parser.parse_args()

    
    handle = ctypes.c_void_p()
    intf = ctypes.POINTER(ctypes.c_ubyte)(args.intf.encode())
    
    res = AVDECC_create(ctypes.byref(handle), intf, adp_cb, acmp_cb, aecp_aem_cb)

    try:
        while(True):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
        
    res = AVDECC_destroy(handle)
