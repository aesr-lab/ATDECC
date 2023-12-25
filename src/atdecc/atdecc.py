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

class EntityModelEntityStateMachine(Thread):
    """
    IEEE 1722.1-2021, section 9.3.5
    """
    
    def __init__(self, entity_info, interfaces, config):
        super(EntityModelEntityStateMachine, self).__init__()
        self.event = Event()
        self.doTerminate = False
        self.interfaces = interfaces
        
        self.rcvdCommand = Queue()
        self.entity_info = entity_info
        self.unsolicited = None
        self.unsolicitedSequenceID = 0
        self.unsolicited_list = set()
        
        self.owner_entity_id = 0 # uint64

        # config
        with open(config, 'r') as cfg:
            self.config = yaml.safe_load(cfg)

    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()
        
    def aecp_aem_cb(self, aecp_aemdu: at.struct_jdksavdecc_aecpdu_common, payload=None):
        if eui64_to_uint64(aecp_aemdu.aecpdu_header.header.target_entity_id) == self.entity_info.entity_id:
            logging.info("AECP AEM: %s", aecpdu_aem_str(aecp_aemdu))

#            print(f"AECP %x: %s"%(aecp_aemdu.aecpdu_header.header.message_type, hexdump(payload[:16])))

            if aecp_aemdu.aecpdu_header.header.message_type == at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND:
                self.rcvdCommand.put((copy.deepcopy(aecp_aemdu), payload)) # copy structure, will probably be overwritten
                self.event.set()

    def acquireEntity(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The acquireEntity function is used to handle the receipt, processing and respond to an ACQUIRE_ENTITY AEM Command (7.4.1).
        
        The acquireEntity function handles checking the current status of the acquisition, issuing any required 
        CONTROLLER_AVAILABLE AEM Command (7.4.4) and dealing with the response and sending any required IN_PROGRESS responses 
        for the passed in command.
        acquireEntity returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command ACQUIRE_ENTITY
 
        logging.debug("ACQUIRE_ENTITY")
        
        aem_acquire_flags, owner_entity_id, descriptor_type, descriptor_index = struct.unpack_from("!LQHH", payload)

        # Generate response struct
        response=at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=copy.deepcopy(command.aecpdu_header),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY,
        )
 
        if descriptor_type == at.JDKSAVDECC_DESCRIPTOR_ENTITY:
            # we only support DESCRIPTOR_ENTITY
            controller_id = eui64_to_uint64(command.aecpdu_header.controller_entity_id)

            if aem_acquire_flags & 0x0000000001:
                # We don't currently handle the persistent flag
                pass
            
            if aem_acquire_flags & 0x8000000000:
                # Release controller if id matches
                if self.owner_entity_id == controller_id:
                    self.owner_entity_id = 0
                    status = at.JDKSAVDECC_AEM_STATUS_SUCCESS
                else:
                    # id doesn't match
                    status = at.JDKSAVDECC_AEM_STATUS_BAD_ARGUMENTS
            else:
                # Acquire controller
                if self.owner_entity_id:
                    # already acquired
                    status = at.JDKSAVDECC_AEM_STATUS_ENTITY_ACQUIRED
                else:
                    self.owner_entity_id = controller_id
                    status = at.JDKSAVDECC_AEM_STATUS_SUCCESS
                
            status = at.JDKSAVDECC_AEM_STATUS_SUCCESS
        else:
            status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

        # We build
        # at.struct_jdksavdecc_aem_command_acquire_entity_response
        # as payload
        resp_payload = struct.pack("!LQHH",
            aem_acquire_flags, # aem_acquire_flags
            self.owner_entity_id, # owner_entity_id
            descriptor_type, # descriptor_type
            descriptor_index, #descriptor_index
        )

        # Make it a response
        response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
        response.aecpdu_header.header.status = status
        
        logging.debug("ACQUIRE_ENTITY done")
        
        return response, resp_payload
        
    def lockEntity(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The lockEntity is used to handle the receipt, processing and respond to an LOCK_ENTITY AEM Command (7.4.2).
        The lockEntity function returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command LOCK_ENTITY

        logging.debug("LOCK_ENTITY")
        
        response = copy.deepcopy(command)
        response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
        response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE

        logging.debug("LOCK_ENTITY done")
        
        return response, bytes()
        
    def entityAvailable(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The lockEntity is used to handle the receipt, processing and respond to an LOCK_ENTITY AEM Command (7.4.2).
        The lockEntity function returns a AEMCommandResponse structure filled in with the appropriate details from the command, 
        an appropriate status code and the Acquired Controller’s Entity ID.
        """
        # handle AEM Command ENTITY_AVAILABLE

        logging.debug("ENTITY_AVAILABLE")
        
        response = copy.deepcopy(command)
        response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
        response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE

        logging.debug("ENTITY_AVAILABLE done")
        
        return response, bytes()


    def processCommand(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        """
        The processCommand is used to handle the receipt, processing and respond to an AEM Command other than 
        ACQUIRE_ENTITY and LOCK_ENTITY.
        
        The processCommand function returns a AEMCommandResponse structure filled in with the appropriate details 
        from the command and an appropriate status code. 
        Any command that is received and not implemented shall be 
        responded to with a correctly sized response and a status of NOT_IMPLEMENTED.
        
        The AEMCommandResponse type (struct_jdksavdecc_aecpdu_common) is a structure containing the fields of a base AEM AECPDU.
        """
        # handle AEM Command other than ACQUIRE_ENTITY and LOCK_ENTITY

        response = None
        response_payload = None
        
        if command.command_type == at.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION:
            eid = eui64_to_uint64(command.aecpdu_header.controller_entity_id)
            self.unsolicited_list.add(eid)
            logging.debug(f"Added eid={eid} to unsolicited_list")

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response_payload = struct.pack("!L", 0)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_DEREGISTER_UNSOLICITED_NOTIFICATION:
            eid = eui64_to_uint64(command.aecpdu_header.controller_entity_id)
            try:
                self.unsolicited_list.remove(eid)
                logging.debug(f"Removed eid={eid} from unsolicited_list")
                status = at.JDKSAVDECC_AEM_STATUS_SUCCESS
            except KeyError:
                status = at.JDKSAVDECC_AEM_STATUS_BAD_ARGUMENTS

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = status
            response_payload = struct.pack("!L", 0)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_READ_DESCRIPTOR:
            em = self.entity_info
            _, _, descriptor_type, descriptor_index = struct.unpack_from("!4H", payload)
            configuration_index = 0 # need to adjust if more than one configuration

            logging.debug("READ_DESCRIPTOR %s", api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type))
            logging.debug("DESCRIPTOR INDEX %d", descriptor_index)

            descriptor = None


            try:
                descriptor = AEMDescriptorFactory.create_descriptor(descriptor_type, descriptor_index, em, self.config)
                response_payload = descriptor.encode()
            except ValueError:
                logging.error("DESCRIPTOR CLASS NOT FOUND")
                traceback.print_exc()
                pass

            
            if descriptor is not None:
                response = copy.deepcopy(command)
                response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
                response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_SUCCESS
                prefix = struct.pack("!2H", configuration_index, 0)
                response_payload = prefix+response_payload

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO:
            descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

            logging.debug("GET_AVB_INFO: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
#            response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!2HQLBBH",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                0, # gptp_grandmaster_id
                0, # propagation_delay
                0, # gptp_domain_number
                0, # flags
                0, # msrp_mappings_count = N
                # N msrp_mappings "BBH" (traffic_class, priority, vlan_id)
            )

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_AS_PATH:
            descriptor_index, _ = struct.unpack_from("!2H", payload)

            logging.debug("GET_AS_PATH: descriptor_index=%d"%descriptor_index)

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!2HQ",
                descriptor_index, # descriptor_index
                1, # count
                self.entity_info.entity_id, # Grandmaster ID
            )

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_AUDIO_MAP:
            descriptor_type, descriptor_index, map_index, _ = struct.unpack_from("!4H", payload)

            logging.debug("GET_AUDIO_MAP: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            response_payload = struct.pack("!6H",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                map_index, # map_index
                2, # number_of_maps
                8, # number_of_mappings
                0, # reserved
                # N * Audio_mappings_format
            )

            m = [(descriptor_index, c, 0, c) for c in range(8)]
            mappings = struct.pack("!32H", *flatten_list(m))
            response_payload = pack_struct(descriptor) #+mappings

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_COUNTERS:
            descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

            logging.debug("GET_COUNTERS: descriptor_type=%s, descriptor_index=%d"%(
                    api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                    descriptor_index)
            )

            response = copy.deepcopy(command)
            response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

            if descriptor_type == at.JDKSAVDECC_DESCRIPTOR_ENTITY:
                counters_valid = 0

            elif descriptor_type == at.JDKSAVDECC_DESCRIPTOR_AVB_INTERFACE:
                counters_valid = 0

            elif descriptor_type == at.JDKSAVDECC_DESCRIPTOR_CLOCK_DOMAIN:
                counters_valid = 0

            elif descriptor_type == at.JDKSAVDECC_DESCRIPTOR_STREAM_INPUT:
                counters_valid = 0

            elif descriptor_type == at.JDKSAVDECC_DESCRIPTOR_STREAM_OUTPUT:
                counters_valid = 0

            elif descriptor_type == at.JDKSAVDECC_DESCRIPTOR_PTP_PORT:
                counters_valid = 0

            response_payload = struct.pack("!2HL",
                descriptor_type, # descriptor_type
                descriptor_index, # descriptor_index
                counters_valid, # counters_valid
            )+bytes(32*4)

        if response is None:
            response = copy.deepcopy(command.aecpdu_header)
            response.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
            response.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
            
        return response, response_payload


    def txResponse(self, response, payload=None):
        """
        The txResponse function transmits an AEM response. 
        It sets the AEM AECPDU fields to the values from the response AEMCommandResponse parameter.
        """
        # transmits an AEM response. It sets the AEM AECPDU fields to the values from the response AEMCommandResponse parameter.
        for intf in self.interfaces:
            intf.send_aecp(response, payload)


    def run(self):
        logging.debug("EntityModelEntityStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_aecp_aem_cb(self.aecp_aem_cb)

        while True:
            self.unsolicited = None
            
            if self.rcvdCommand.empty():
                self.event.wait(1)
                # signalled
                self.event.clear()
                
            if self.doTerminate:
                break
            
            try:
                cmd, payload = self.rcvdCommand.get_nowait()
            except Empty:
                cmd = None
            
            try:
                if self.unsolicited is not None:
                    # UNSOLICITED RESPONSE
                    logging.debug("Unsolidated response")
                    self.unsolicited.sequence_id = self.unsolicitedSequenceID
                    self.txResponse(self.unsolicited)
                    self.unsolicitedSequenceID += 1
                    self.unsolicited = None
                
                if cmd is not None:
                    # RECEIVED COMMAND
                    response_payload = None
                    
                    if cmd.command_type == at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY:
                        response, response_payload = self.acquireEntity(cmd, payload)
#                        pdb.set_trace()
                        
                    elif cmd.command_type == at.JDKSAVDECC_AEM_COMMAND_LOCK_ENTITY:
                        response, response_payload = self.lockEntity(cmd, payload)
                    elif cmd.command_type == at.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE:
                        response, response_payload = self.entityAvailable(cmd, payload)
                    else:
                        response, response_payload = self.processCommand(cmd, payload)
                    
                    if response is not None:
                        self.txResponse(response, response_payload)
                    else:
                        logging.warning("Response is None")
                    
            except Exception as e:
                traceback.print_exc();
#                logging.error("Exception: %s", e)

        for intf in self.interfaces:
            intf.unregister_aecp_aem_cb(self.aecp_aem_cb)

        logging.debug("EntityModelEntityStateMachine: Ending thread")


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
