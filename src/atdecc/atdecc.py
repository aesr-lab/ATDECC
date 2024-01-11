#!/usr/bin/env python3

import ctypes
import struct
import time
import logging
from threading import Thread, Event
from queue import Queue, Empty
import copy
import random
import traceback
import pdb

import yaml


from . import atdecc_api as av
from .atdecc_api import ATDECC_create, ATDECC_destroy, ATDECC_send

from .pdu import *
from .pdu_print import *
from .aem import *
from .adp import *
from .acmp import *
from .aecp import *

class jdksInterface:
    handles = {}
    
    def __init__(self, ifname):
        self.ifname = ifname
        
        self.adp_cbs = []
        self.acmp_cbs = []
        self.aecp_aem_cbs = []

        self.handle = ctypes.c_void_p()
        intf = ctypes.c_char_p(self.ifname.encode())
        res = ATDECC_create(ctypes.byref(self.handle), 
                            intf, 
                            self._adp_cb, 
                            self._acmp_cb, 
                            self._aecp_aem_cb
                            )
        assert res == 0
        logging.debug("ATDECC_create done")
        jdksInterface.handles[self.handle.value] = self  # register instance
    
    def __del__(self):
        res = ATDECC_destroy(self.handle)
        logging.debug("ATDECC_destroy done")
        assert res == 0
        del self.handles[self.handle.value]  # unregister instance
        self.handle.value = None
    
    def send_adp(self, msg, entity):
        pdu = entity.get_adpdu()
#        logging.debug("ATDECC_send_adp: %s", adpdu_str(pdu))
        frame = adp_form_msg(pdu, msg, uint64_to_eui64(entity.entity_id))
        res = ATDECC_send(self.handle, frame)
        assert res == 0

    def send_aecp(self, pdu, payload):
#        logging.debug(f"ATDECC_send_aecp: %s", aecpdu_aem_str(pdu))
        frame = aecp_form_msg(pdu, command_payload=payload)
#        if frame.payload:
#            logging.debug("frame payload: %s", bytes(frame.payload).hex())
        res = ATDECC_send(self.handle, frame)

    def send_acmp(self, pdu, message_type, status):
        frame = acmp_form_msg(pdu, message_type, status)
        # if frame.payload:
        #     logging.debug("frame payload: %s", bytes(frame.payload).hex())
        res = ATDECC_send(self.handle, frame)

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

    @at.ATDECC_ADP_CALLBACK
    def _adp_cb(handle, frame_ptr, adpdu_ptr):
        this = jdksInterface.handles[handle]
        du = adpdu_ptr.contents
        if len(this.adp_cbs) == 0:
            logging.debug("Unhandled ADP: %s - %s", adpdu_str(du), this.adp_cbs)
        else:
            for cb in this.adp_cbs:
                cb(du)

    @at.ATDECC_ACMP_CALLBACK
    def _acmp_cb(handle, frame_ptr, acmpdu_ptr):
        this = jdksInterface.handles[handle]
        du = acmpdu_ptr.contents
        if len(this.acmp_cbs) == 0:
            logging.debug("Unhandled ACMP: %s", acmpdu_str(du))
        else:
            for cb in this.acmp_cbs:
                cb(du)

    @at.ATDECC_AECP_AEM_CALLBACK
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


# An ATDECC Talker or Listener shall implement and respond to the 
# ACQUIRE_ENTITY, LOCK_ENTITY, and ENTITY_AVAILABLE commands. 
# All other commands are optional for an ATDECC Talker or Listener.


class AVDECC:

    def __init__(self, intf, entity_info, config, discover=False):
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
        aem_sm = EntityModelEntityStateMachine(entity_info=self.entity_info, interfaces=(self.intf,), config=config)
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
