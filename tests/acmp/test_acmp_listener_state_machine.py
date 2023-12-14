import pytest
from unittest.mock import patch, Mock
import time

from atdecc.adp import EntityInfo
from atdecc.acmp import ACMPListenerStateMachine
from atdecc.acmp.struct import *
from atdecc import Interface, jdksInterface
import atdecc.atdecc_api as at
from atdecc.util import *

class TestACMPListenerStateMachine:

    def test_valid_listener_unique(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        assert alsm.validListenerUnique(42)
        assert not alsm.validListenerUnique(43)

    def test_listener_is_connected(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        # listenerStreamInfos is empty
        assert not alsm.listenerIsConnected(command)

        # connected is TRUE and talker_entity_id/talker_unique_id DOES NOT MATCH talker_entity_id/talker_unique_id in the command
        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(44),
                talker_unique_id = 1,
                connected = True
            )
        }

        assert alsm.listenerIsConnected(command)

        # pending_connections is TRUE and talker_entity_id/talker_unique_id DOES NOT MATCH talker_entity_id/talker_unique_id in the command
        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(44),
                talker_unique_id = 1,
                pending_connections = True
            )
        }

        assert alsm.listenerIsConnected(command)


        # multiple stream infos present
        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(44),
                talker_unique_id = 1,
                connected = True
            ),
            1: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(43),
                talker_unique_id = 0,
                pending_connections = True
            )
        }

        assert alsm.listenerIsConnected(command)

        # This function returns FALSE when being asked if it is connected to the same stream
        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(43),
                talker_unique_id = 0,
                connected = True
            )
        }

        assert not alsm.listenerIsConnected(command)

    def test_listener_is_connected_to(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        # listenerStreamInfos is empty
        assert not alsm.listenerIsConnectedTo(command)

        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(43),
                talker_unique_id=1,
                connected = True
            )
        }

        assert not alsm.listenerIsConnectedTo(command)

        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(44),
                talker_unique_id=0,
                pending_connections = True
            )
        }

        assert not alsm.listenerIsConnectedTo(command)

        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(43),
                talker_unique_id=0,
                connected = True
            )
        }

        assert alsm.listenerIsConnectedTo(command)

        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(43),
                talker_unique_id=0,
                connected=True
            ),
            1: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(44),
                talker_unique_id=1,
                pending_connections=True
            )
        }

        assert alsm.listenerIsConnectedTo(command)

    def test_tx_command_without_retry(self):
        """
        without retry
        If this function successfully sends the message and it is not a retry 
        then it adds an InflightCommand entry to the inflight variable 
        with the command field set to the passed in command, 
        the timeout field set to the value of currentTime + the appropriate timeout for the messageType (see Table 8­1), 
        the retried field set to FALSE and the sequence_id field set to the sequence_id used for the transmitted message.
        """

        ei = EntityInfo(entity_id=42)
        intf = Interface("eth0")
        alsm = ACMPListenerStateMachine(ei, [intf])

        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0,
            sequence_id=13
        )

        intf.send_acmp = Mock()

        # initially the inflight list is empty
        assert not alsm.inflight

        return_value = alsm.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, command, False)

        inflightCommand = alsm.inflight[0]

        assert return_value
        assert not inflightCommand.retried
        assert 13 == inflightCommand.original_sequence_id
        # assert inflightCommand.timeout > time.time() * 1000

        intf.send_acmp.assert_called_with(command, at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, at.JDKSAVDECC_ACMP_STATUS_SUCCESS)

    def test_tx_command_with_retry(self):
        """
        with retry
        If this function successfully sends the message and it is a retry 
        then it updates the InflightCommand entry of the inflight variable 
        corresponding with this command by setting the timeout field to the value of currentTime + the appropriate timeout 
        for the messageType (see Table 8­1) and the retried field set to TRUE. 
        This starts the timeout timer for this command.
        """

        ei = EntityInfo(entity_id=42)
        intf = Interface("eth0")
        alsm = ACMPListenerStateMachine(ei, [intf])

        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0,
            sequence_id=13
        )
        intf.send_acmp = Mock()

        # initially the inflight list contains one entry
        alsm.inflight = [
            struct_acmp_inflight_command(
                timeout=int(time.time()*1000) + at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_TX_COMMAND_MS,
                retried=False,
                command=command,
                original_sequence_id=13
            )
        ]
        
        return_value = alsm.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, command, True)

        inflightCommand = alsm.inflight[0]

        assert return_value
        assert inflightCommand.retried
        assert 13 == inflightCommand.original_sequence_id
        # assert inflightCommand.timeout > time.time() * 1000

        intf.send_acmp.assert_called_with(command, at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, at.JDKSAVDECC_ACMP_STATUS_SUCCESS)

    def test_tx_command_failed(self):
        """
        If this function fails to send the message (e.g., there are no available InFlightCommand entries to use) 
        then it calls the txResponse function with the appropriate response code for the messageType (messageType + 1), 
        the passed in command and the status code of COULD_NOT_SEND_MESSAGE. 
        If this was a retry then the InFlightCommand entry corresponding to the command is removed from the inflight variable.
        """

        ei = EntityInfo(entity_id=42)
        intf = Interface("eth0")
        alsm = ACMPListenerStateMachine(ei, [intf])

        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0,
            sequence_id=13
        )

        intf.send_acmp = Mock()
        alsm.txResponse = Mock()

        return_value = alsm.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, command, True)

        assert not return_value

        # message type is incremented by one
        alsm.txResponse.assert_called_with(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_RESPONSE, command, at.JDKSAVDECC_ACMP_STATUS_COULD_NOT_SEND_MESSAGE)


    def test_tx_response(self):
        ei = EntityInfo(entity_id=42)
        intf = Interface("eth0")
        alsm = ACMPListenerStateMachine(ei, [intf])

        # CONNECT_TX_TIMEOUT
        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        intf.send_acmp = Mock()

        alsm.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, response, at.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)

        intf.send_acmp.assert_called_with(response, at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, at.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)

        # DISCONNECT_TX_TIMEOUT
        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        intf.send_acmp = Mock()

        alsm.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, at.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)

        intf.send_acmp.assert_called_with(response, at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, at.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)

        # CONNECT RX COMMAND
        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        intf.send_acmp = Mock()

        alsm.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, response, at.JDKSAVDECC_ACMP_STATUS_CONTROLLER_NOT_AUTHORIZED)

        intf.send_acmp.assert_called_with(response, at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, at.JDKSAVDECC_ACMP_STATUS_CONTROLLER_NOT_AUTHORIZED)

    def test_connect_listener(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        returned_response, status = alsm.connectListener(response)

        # assert stream info struct is set
        assert alsm.listenerStreamInfos[0].connected
        assert 43 == eui64_to_uint64(alsm.listenerStreamInfos[0].talker_entity_id)
        assert 0 == alsm.listenerStreamInfos[0].talker_unique_id
        assert not alsm.listenerStreamInfos[0].pending_connection

        # assert return values
        assert at.JDKSAVDECC_ACMP_STATUS_SUCCESS == status
        assert response == returned_response

    def test_disconnect_listener(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(44),
            talker_unique_id=1,
            listener_unique_id=1
        )

        returned_response, status = alsm.disconnectListener(response)

        # assert stream info struct is set
        assert not alsm.listenerStreamInfos[1].connected
        assert 0 == eui64_to_uint64(alsm.listenerStreamInfos[1].talker_entity_id)
        assert 0 == eui64_to_uint64(alsm.listenerStreamInfos[1].controller_entity_id)
        assert 0 == eui64_to_uint64(alsm.listenerStreamInfos[1].stream_id)
        assert 0 == eui48_to_uint64(alsm.listenerStreamInfos[1].stream_dest_mac)
        assert 0 == alsm.listenerStreamInfos[1].talker_unique_id
        assert 0 == alsm.listenerStreamInfos[1].flags
        assert 0 == alsm.listenerStreamInfos[1].stream_vlan_id
        assert not alsm.listenerStreamInfos[1].pending_connection

        # assert return values
        assert at.JDKSAVDECC_ACMP_STATUS_SUCCESS == status
        assert response == returned_response

    def test_cancel_timeout(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        # commandResponse is a copy of the command entry within inflight
        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        alsm.inflight = [
            struct_acmp_inflight_command(
                timeout=at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_TX_COMMAND_MS,
                retried=False,
                command=command,
                original_sequence_id=0
            ) 
        ]

        alsm.cancelTimeout(command)

        assert 0 == alsm.inflight[0].timeout

        # commandResponse is a response for the command entry within inflight
        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        alsm.inflight = [
            struct_acmp_inflight_command(
                timeout=at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_RX_COMMAND_MS,
                retried=False,
                command=command,
                original_sequence_id=0
            ) 
        ]

        alsm.cancelTimeout(response)

        assert 0 == alsm.inflight[0].timeout

    def test_remove_inflight(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])

        # commandResponse is a copy of the command entry within inflight
        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        alsm.inflight = [
            struct_acmp_inflight_command(
                timeout=at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_TX_COMMAND_MS,
                retried=False,
                command=command,
                original_sequence_id=0
            )
        ]

        alsm.removeInflight(command)

        assert not alsm.inflight

        # commandResponse is a response for the command entry within inflight
        response = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        alsm.inflight = [
            struct_acmp_inflight_command(
                timeout=at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_RX_COMMAND_MS,
                retried=False,
                command=command,
                original_sequence_id=0
            ) 
        ]

        alsm.removeInflight(response)

        assert not alsm.inflight

    def test_get_state(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])
        alsm.listenerStreamInfos = {
            0: struct_acmp_listener_stream_info(
                talker_entity_id=uint64_to_eui64(43),
                talker_unique_id = 0,
                connected = True
            )
        }
        
        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_COMMAND
            ),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        response, status = alsm.getState(command)

        assert at.JDKSAVDECC_ACMP_STATUS_SUCCESS == status

        assert at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_RESPONSE == response.header.message_type
        assert eui64_to_uint64(command.header.stream_id) == eui64_to_uint64(response.header.stream_id)
        assert eui48_to_uint64(command.stream_dest_mac) == eui48_to_uint64(response.stream_dest_mac)
        assert 1 == response.connection_count
        assert command.flags == response.flags
        assert eui64_to_uint64(command.talker_entity_id) == eui64_to_uint64(response.talker_entity_id)
        assert command.talker_unique_id == response.talker_unique_id

    def test_listener_is_acquired_or_locked_by_other(self):
        ei = EntityInfo(entity_id=42)
        alsm = ACMPListenerStateMachine(ei, [])
        
        command = at.struct_jdksavdecc_acmpdu (
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_COMMAND
            ),
            controller_entity_id=uint64_to_eui64(42),
            talker_entity_id=uint64_to_eui64(43),
            talker_unique_id=0,
            listener_unique_id=0
        )

        # TODO see comment in implementation
        assert not alsm.listenerIsAcquiredOrLockedByOther(command)
