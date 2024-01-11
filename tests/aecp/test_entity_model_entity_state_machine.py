import pytest
from unittest.mock import patch, Mock, ANY
import time
import yaml

from atdecc.adp import EntityInfo
from atdecc.aecp import EntityModelEntityStateMachine
from atdecc import Interface, jdksInterface
import atdecc.atdecc_api as at
from atdecc.util import *

class TestEntityModelEntityStateMachine:

    ### Test State Machine Functions

    def test_acquire_entity_release_match(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        emesm.owner_entity_id = 43
        
        payload = struct.pack("!QQHH",
            # RELEASE
            0x8000000000,
            43,
            at.JDKSAVDECC_DESCRIPTOR_ENTITY,
            0
        )

        response, resp_payload = emesm.acquireEntity(at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
        ), payload)

        assert at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY == response.command_type
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_SUCCESS == response.aecpdu_header.header.status
        # controller id is released
        assert 0 == emesm.owner_entity_id
        
    def test_acquire_entity_release_mismatch(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        emesm.owner_entity_id = 44
        
        payload = struct.pack("!QQHH",
            # RELEASE
            0x8000000000,
            43,
            at.JDKSAVDECC_DESCRIPTOR_ENTITY,
            0
        )

        response, resp_payload = emesm.acquireEntity(at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
        ), payload)

        assert at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY == response.command_type
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_BAD_ARGUMENTS == response.aecpdu_header.header.status

    def test_acquire_entity_already_acquired(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        emesm.owner_entity_id = 43
        
        payload = struct.pack("!QQHH",
            0x0000000000,
            43,
            at.JDKSAVDECC_DESCRIPTOR_ENTITY,
            0
        )

        response, resp_payload = emesm.acquireEntity(at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
        ), payload)

        assert at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY == response.command_type
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_ENTITY_ACQUIRED == response.aecpdu_header.header.status

    def test_acquire_entity_acquire(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        
        payload = struct.pack("!QQHH",
            0x0000000000,
            43,
            at.JDKSAVDECC_DESCRIPTOR_ENTITY,
            0
        )

        response, resp_payload = emesm.acquireEntity(at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
        ), payload)

        assert at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY == response.command_type
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_SUCCESS == response.aecpdu_header.header.status
        assert 43 == emesm.owner_entity_id

    def test_lock_entity(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        response, resp_payload = emesm.lockEntity(at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_LOCK_ENTITY
        ), bytes())
    
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED == response.aecpdu_header.header.status


    def test_tx_response(self):
        ei = EntityInfo(entity_id=42)
        intf = Interface("eth0")
        emesm = EntityModelEntityStateMachine(ei, [intf], "./tests/fixtures/config.yml")

        response=at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
                ),
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY,
        )
        
        intf.send_aecp = Mock()

        emesm.txResponse(response)

        intf.send_aecp.assert_called_with(response, None)


    def test_process_command_entity_available(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE)

        emesm._handleEntityAvailable = Mock()
        emesm._handleEntityAvailable.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleEntityAvailable.assert_called()


    def test_process_command_register_unsolicited_notification(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION)

        emesm._handleRegisterUnsolicitedNotification = Mock()
        emesm._handleRegisterUnsolicitedNotification.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleRegisterUnsolicitedNotification.assert_called()


    def test_process_command_deregister_unsolicited_notification(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_DEREGISTER_UNSOLICITED_NOTIFICATION)

        emesm._handleDeregisterUnsolicitedNotification = Mock()
        emesm._handleDeregisterUnsolicitedNotification.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleDeregisterUnsolicitedNotification.assert_called()


    def test_process_command_read_descriptor(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_READ_DESCRIPTOR)

        emesm._handleReadDescriptor = Mock()
        emesm._handleReadDescriptor.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleReadDescriptor.assert_called()


    def test_process_command_get_avb_info(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO)

        emesm._handleGetAvbInfo = Mock()
        emesm._handleGetAvbInfo.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleGetAvbInfo.assert_called()


    def test_process_command_get_as_path(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_AS_PATH)

        emesm._handleGetAsPath = Mock()
        emesm._handleGetAsPath.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleGetAsPath.assert_called()


    def test_process_command_get_audio_map(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_AUDIO_MAP)

        emesm._handleGetAudioMap = Mock()
        emesm._handleGetAudioMap.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleGetAudioMap.assert_called()


    def test_process_command_get_counters(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_COUNTERS)

        emesm._handleGetCounters = Mock()
        emesm._handleGetCounters.return_value = [command, bytes()]

        response, resp_payload = emesm.processCommand(command, bytes())
    
        emesm._handleGetCounters.assert_called()


    ### Test State Machine Paths
    # UNSOLICITED_RESPONSE
    def test_unsolicited_response(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        
        unsolicited = at.struct_jdksavdecc_aecpdu_aem(
            header = at.struct_jdksavdecc_aecpdu_common_control_header(
                message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                target_entity_id=uint64_to_eui64(42)
            ),
            sequence_id=13,
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
            )

        emesm.txResponse = Mock()

        emesm.start()

        emesm.unsolicited = unsolicited
        emesm.unsolicitedSequenceID = 127

        emesm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        assert 128 == emesm.unsolicitedSequenceID
        assert not emesm.unsolicited
        emesm.txResponse.assert_called_with(unsolicited)

        emesm.performTerminate()


    # RECEIVED_COMMAND
    # rcvdAEMCommand && rcvdCommand.target_entity_id == myEntityID
    def test_received_command_acquire_entity(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            header = at.struct_jdksavdecc_aecpdu_common_control_header(
                message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                target_entity_id=uint64_to_eui64(42)
            ),
            sequence_id=13,
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
            )

        emesm.acquireEntity = Mock()
        emesm.acquireEntity.return_value = [command, bytes()]
        emesm.txResponse = Mock()

        emesm.start()

        emesm.rcvdCommand.put((command, None))

        emesm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        emesm.acquireEntity.assert_called()
        emesm.txResponse.assert_called_with(command, bytes())

        emesm.performTerminate()


    def test_received_command_lock_entity(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        
        command = at.struct_jdksavdecc_aecpdu_aem(
            header = at.struct_jdksavdecc_aecpdu_common_control_header(
                message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                target_entity_id=uint64_to_eui64(42)
            ),
            sequence_id=13,
            command_type=at.JDKSAVDECC_AEM_COMMAND_LOCK_ENTITY
            )

        emesm.lockEntity = Mock()
        emesm.lockEntity.return_value = [command, bytes()]
        emesm.txResponse = Mock()

        emesm.start()

        emesm.rcvdCommand.put((command, None))

        emesm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        emesm.lockEntity.assert_called()
        emesm.txResponse.assert_called_with(command, bytes())

        emesm.performTerminate()


    def test_received_command_entity_available(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        
        command = at.struct_jdksavdecc_aecpdu_aem(
            header = at.struct_jdksavdecc_aecpdu_common_control_header(
                message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                target_entity_id=uint64_to_eui64(42)
            ),
            sequence_id=13,
            command_type=at.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE
            )

        emesm.processCommand = Mock()
        emesm.processCommand.return_value = [command, bytes()]
        emesm.txResponse = Mock()

        emesm.start()

        emesm.rcvdCommand.put((command, None))

        emesm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        emesm.processCommand.assert_called()
        emesm.txResponse.assert_called_with(command, bytes())

        emesm.performTerminate()


    def test_received_command_read_descriptor(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        
        command = at.struct_jdksavdecc_aecpdu_aem(
            header = at.struct_jdksavdecc_aecpdu_common_control_header(
                message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                target_entity_id=uint64_to_eui64(42)
            ),
            sequence_id=13,
            command_type=at.JDKSAVDECC_AEM_COMMAND_READ_DESCRIPTOR
            )

        emesm.processCommand = Mock()
        emesm.processCommand.return_value = [command, bytes()]
        emesm.txResponse = Mock()

        emesm.start()

        emesm.rcvdCommand.put((command, None))

        emesm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        emesm.processCommand.assert_called()
        emesm.txResponse.assert_called_with(command, bytes())

        emesm.performTerminate()


    def test_noop(self):
        ei = EntityInfo(entity_id=43)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")

        command = at.struct_jdksavdecc_aecpdu_aem(
            header = at.struct_jdksavdecc_aecpdu_common_control_header(
                message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                target_entity_id=uint64_to_eui64(42)
            ),
            sequence_id=13,
            command_type=at.JDKSAVDECC_AEM_COMMAND_ACQUIRE_ENTITY
            )

        emesm.txResponse = Mock()

        emesm.start()

        emesm.rcvdCommand.put((command, None))

        emesm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        emesm.txResponse.assert_not_called()

        emesm.performTerminate()


    ### Test State Machine Handlers

    def test_entity_available_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_ENTITY_AVAILABLE
        )

        response, payload = emesm._handleEntityAvailable(command, None)
        
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED == response.aecpdu_header.header.status


    def test_register_unsolicited_notification_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION
        )

        response, payload = emesm._handleRegisterUnsolicitedNotification(command, None)
        
        assert 1 == len(emesm.unsolicited_list)
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_SUCCESS == response.aecpdu_header.header.status


    def test_deregister_unsolicited_notification_handler(self):
        # unsolicited list match
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        emesm.unsolicited_list = {43}

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION
        )

        response, payload = emesm._handleDeregisterUnsolicitedNotification(command, None)
        
        assert 0 == len(emesm.unsolicited_list)
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_SUCCESS == response.aecpdu_header.header.status

        # unsolicited list mismatch
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        emesm.unsolicited_list = {44}

        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_REGISTER_UNSOLICITED_NOTIFICATION
        )

        response, payload = emesm._handleDeregisterUnsolicitedNotification(command, None)
        
        assert 1 == len(emesm.unsolicited_list)
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_BAD_ARGUMENTS == response.aecpdu_header.header.status


    def test_get_avb_info_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO
        )

        payload = struct.pack("!2H",
                              at.JDKSAVDECC_DESCRIPTOR_ENTITY,
                              0)

        response, resp_payload = emesm._handleGetAvbInfo(command, payload)
        
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_SUCCESS == response.aecpdu_header.header.status


    def test_get_as_path_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_AVB_INFO
        )

        payload = struct.pack("!2H",
                              at.JDKSAVDECC_DESCRIPTOR_ENTITY,
                              0)

        response, resp_payload = emesm._handleGetAsPath(command, payload)
        
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED == response.aecpdu_header.header.status


    def test_get_audio_map_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_AUDIO_MAP
        )

        payload = struct.pack("!4H",
                              at.JDKSAVDECC_DESCRIPTOR_ENTITY,
                              0,
                              0,
                              0)

        response, resp_payload = emesm._handleGetAudioMap(command, payload)
        
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED == response.aecpdu_header.header.status


    def test_get_counters_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_GET_COUNTERS
        )

        payload = struct.pack("!2H",
                              at.JDKSAVDECC_DESCRIPTOR_ENTITY,
                              0)

        response, resp_payload = emesm._handleGetCounters(command, payload)
        
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_NOT_IMPLEMENTED == response.aecpdu_header.header.status


    def test_read_descriptor_handler(self):
        ei = EntityInfo(entity_id=42)
        emesm = EntityModelEntityStateMachine(ei, [], "./tests/fixtures/config.yml")
        command = at.struct_jdksavdecc_aecpdu_aem(
            aecpdu_header=at.struct_jdksavdecc_aecpdu_common(
                header = at.struct_jdksavdecc_aecpdu_common_control_header(
                    message_type=at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND,
                    target_entity_id=uint64_to_eui64(42)
            ),
                controller_entity_id=uint64_to_eui64(43),
                sequence_id=13
            ),
            command_type=at.JDKSAVDECC_AEM_COMMAND_READ_DESCRIPTOR
        )

        payload = struct.pack("!4H",
                              0,
                              0,
                              at.JDKSAVDECC_DESCRIPTOR_ENTITY,
                              0)

        response, resp_payload = emesm._handleReadDescriptor(command, payload)
        
        assert at.JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE == response.aecpdu_header.header.message_type
        assert at.JDKSAVDECC_AEM_STATUS_SUCCESS == response.aecpdu_header.header.status
