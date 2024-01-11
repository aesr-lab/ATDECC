from threading import Thread, Event
from queue import Queue, Empty
import copy
import logging
import traceback
import yaml

from .. import atdecc_api as at
from ..util import *
from ..pdu_print import *
from ..aem import AEMDescriptorFactory

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
        self.rcvdAEMCommand = False
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
                self.rcvdAEMCommand = True
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
        
        aem_acquire_flags, owner_entity_id, descriptor_type, descriptor_index = struct.unpack_from("!QQHH", payload)

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
            
            # RELEASE flag
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
        else:
            status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

        # We build
        # at.struct_jdksavdecc_aem_command_acquire_entity_response
        # as payload
        resp_payload = struct.pack("!QQHH",
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

        
    def _handleEntityAvailable(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        logging.debug("ENTITY_AVAILABLE")
        
        response = copy.deepcopy(command)
        response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED
        response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE

        logging.debug("ENTITY_AVAILABLE done")
        
        return response, bytes()


    def _handleRegisterUnsolicitedNotification(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        eid = eui64_to_uint64(command.aecpdu_header.controller_entity_id)
        self.unsolicited_list.add(eid)
        logging.debug(f"Added eid={eid} to unsolicited_list")

        response = copy.deepcopy(command)
        response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
        response_payload = struct.pack("!L", 0)
        
        return response, response_payload


    def _handleDeregisterUnsolicitedNotification(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
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

        return response, response_payload

    def _handleGetAvbInfo(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
        descriptor_type, descriptor_index = struct.unpack_from("!2H", payload)

        logging.debug("GET_AVB_INFO: descriptor_type=%s, descriptor_index=%d"%(
                api_enum('JDKSAVDECC_DESCRIPTOR_', descriptor_type),
                descriptor_index)
        )

        response = copy.deepcopy(command)
        response.aecpdu_header.header.message_type = at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
#        response.aecpdu_header.header.status = at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED

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

        return response, response_payload

    
    def _handleGetAsPath(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
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

        return response, response_payload


    def _handleGetAudioMap(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
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
        # TODO get this from factory
        # response_payload = pack_struct(descriptor) #+mappings

        return response, response_payload

    def _handleGetCounters(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
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

        return response, response_payload


    def _handleReadDescriptor(self, command: at.struct_jdksavdecc_aecpdu_aem, payload):
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

        return response, response_payload


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

        if command.command_type == at.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE:
            response, response_payload = self._handleEntityAvailable(command, payload)
        
        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION:
            response, response_payload = self._handleRegisterUnsolicitedNotification(command, payload)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_DEREGISTER_UNSOLICITED_NOTIFICATION:
            response, response_payload = self._handleDeregisterUnsolicitedNotification(command, payload)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_READ_DESCRIPTOR:
            response, response_payload = self._handleReadDescriptor(command, payload)
            
        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO:
            response, response_payload = self._handleGetAvbInfo(command, payload)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_AS_PATH:
            response, response_payload = self._handleGetAsPath(command, payload)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_AUDIO_MAP:
            response, response_payload = self._handleGetAudioMap(command, payload)

        elif command.command_type == at.JDKSAVDECC_AEM_COMMAND_GET_COUNTERS:
            response, response_payload = self._handleGetCounters(command, payload)

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
                        
                    elif cmd.command_type == at.JDKSAVDECC_AEM_COMMAND_LOCK_ENTITY:
                        response, response_payload = self.lockEntity(cmd, payload)
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
