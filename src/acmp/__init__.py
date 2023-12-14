import atdecc_api as at
from adp import GlobalStateMachine
from acmp.struct import *
from util import *
from pdu_print import *

from threading import Thread, Event
from queue import Queue, Empty
import copy
import logging
import traceback

timeout_values = {
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_TX_COMMAND_MS,
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_DISCONNECT_TX_COMMAND_MS,
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_TX_STATE_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_GET_TX_STATE_COMMAND,
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_CONNECT_RX_COMMAND_MS,
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_DISCONNECT_RX_COMMAND_MS,
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_GET_RX_STATE_COMMAND_MS,
    at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_TX_CONNECTION_COMMAND: at.JDKSAVDECC_ACMP_TIMEOUT_GET_TX_CONNECTION_COMMAND,
}

class ACMPListenerStateMachine(
    GlobalStateMachine,
    Thread
    ):
    """
    IEEE 1722.1-2021, section 8.2.4
    """
    
    def __init__(self, entity_info, interfaces):
        super(ACMPListenerStateMachine, self).__init__()
        self.event = Event()
        # a structure of type ACMPCommandResponse containing the next received ACMPDUtobe processed
        self.rcvdCmdResp = Queue()
        self.doTerminate = False
        self.interfaces = interfaces
        
        self.my_id = entity_info.entity_id
        self.inflight = []
        self.listenerStreamInfos = {}
        self.rcvdConnectRXCmd = False
        self.rcvdDisconnectRXCmd = False
        self.rcvdConnectTXResp = False
        self.rcvdDisconnectTXResp = False
        self.rcvdGetRXState = False

    def performTerminate(self):
        self.doTerminate = True
        logging.debug("doTerminate")
        self.event.set()

    def acmp_cb(self, acmpdu: at.struct_jdksavdecc_acmpdu):
        if eui64_to_uint64(acmpdu.listener_entity_id) == self.my_id:
            logging.info("ACMP: %s", acmpdu_str(acmpdu))
            self.rcvdCmdResp.put(copy.deepcopy(acmpdu)) # copy structure (will probably be overwritten)
            self.event.set()

    def validListenerUnique(self, ListenerUniqueId):
        """
        The validListenerUnique function returns a Boolean indicating if the 
        ATDECC ListenerUniqueId passed in is valid for the ATDECC Entity.
        """
        return ListenerUniqueId == self.my_id

    def listenerIsConnected(self, command):
        """
        The listenerIsConnected function returns a Boolean indicating if the 
        ATDECC Listener is already connected to or attempting to connect to a 
        stream source other than the one specified by the talker_entity_id and talker_unique_id in the command.
        
        This function returns TRUE if either connected is TRUE or pending_connections is TRUE 
        and talker_entity_id and talker_unique_id in the command does not matches 
        talker_entity_id and talker_unique_id in the listenerStreamInfos entry otherwise it returns FALSE.

        TODO it's not quite clear if this means "the entry in listerStreamInfos denoted by the listener_unique_id"
        
        NOTE: This function returns FALSE when being asked if it is connected to the 
        same stream so that after an unclean disconnection (the ATDECC Talker disappearing 
        and then reappearing without an intermediate DISCONNECT_RX_COMMAND being sent) 
        the next connection attempt by the ATDECC Controller to restore the connection will succeed.
        """

        try:
            streamInfo = self.listenerStreamInfos[command.listener_unique_id]

            return (
                (eui64_to_uint64(streamInfo.talker_entity_id) != eui64_to_uint64(command.talker_entity_id) and 
                streamInfo.talker_unique_id != command.talker_unique_id) and
                (streamInfo.connected or streamInfo.pending_connections)
            )
        except KeyError:
            return False


    def listenerIsConnectedTo(self, command):
        """
        The listenerIsConnectedTo function returns a Boolean indicating 
        if the ATDECC Listener is already connected to the stream source 
        specified by the talker_entity_id and talker_unique_id in the command.
        
        This function returns TRUE if connected is TRUE and talker_entity_id 
        and talker_unique_id in the command matches talker_entity_id and talker_unique_id 
        in the listenerStreamInfos entry otherwise it returns FALSE.
        """
        try:
            streamInfo = self.listenerStreamInfos[command.listener_unique_id]

            return (
                eui64_to_uint64(streamInfo.talker_entity_id) == eui64_to_uint64(command.talker_entity_id) and 
                streamInfo.talker_unique_id == command.talker_unique_id
            )
        except KeyError:
            return False

    def txCommand(self, messageType, command, retry):
        """
        The txCommand function transmits a command of type messageType. 
        It sets the ACMPDU fields to the values from the command 
        ACMPCommandResponse parameter and the message_type field to the value of messageType.
        
        If this function successfully sends the message and it is not a retry 
        then it adds an InflightCommand entry to the inflight variable 
        with the command field set to the passed in command, 
        the timeout field set to the value of currentTime + the appropriate timeout for the messageType (see Table 8­1), 
        the retried field set to FALSE and the sequence_id field set to the sequence_id used for the transmitted message. 
        This starts the timeout timer for this command.
        
        If this function successfully sends the message and it is a retry 
        then it updates the InflightCommand entry of the inflight variable 
        corresponding with this command by setting the timeout field to the value of currentTime + the appropriate timeout 
        for the messageType (see Table 8­1) and the retried field set to TRUE. 
        This starts the timeout timer for this command.
        
        If this function fails to send the message (e.g., there are no available InFlightCommand entries to use) 
        then it calls the txResponse function with the appropriate response code for the messageType (messageType + 1), 
        the passed in command and the status code of COULD_NOT_SEND_MESSAGE. 
        If this was a retry then the InFlightCommand entry corresponding to the command is removed from the inflight variable.
        
        This function returns TRUE if it sent a command or FALSE otherwise.
        """

        try:
            if retry:
                matching_inflight_index = self.findMatchingInflightIndex(command)
                if matching_inflight_index is not None:
                    inflightCommand = self.inflight[matching_inflight_index]
                    inflightCommand.retried = True
                    inflightCommand.timeout = int(self.currentTime * 1000) + timeout_values[messageType]

                    self._tx(command, messageType, at.JDKSAVDECC_ACMP_STATUS_SUCCESS)

                    return True
                else:
                    self.txResponse(messageType + 1, command, at.JDKSAVDECC_ACMP_STATUS_COULD_NOT_SEND_MESSAGE)

                    return False
            else:
                self.inflight.append(struct_acmp_inflight_command(
                    timeout=int(self.currentTime * 1000) + timeout_values[messageType],
                    retried=False,
                    command=command,
                    original_sequence_id=command.sequence_id
                ))

                self._tx(command, messageType, at.JDKSAVDECC_ACMP_STATUS_SUCCESS)

                return True
        except:
            return False

    def txResponse(self, messageType, response, error):
        """
        The txResponse function transmits a response of type messageType. 
        It sets the ACMPDU fields to the values from the response parameter, 
        the message_type field to the value of messageType and the status field to the value of the error parameter.
        """
        self._tx(response, messageType, error)

    def _tx(self, commandResponse, messageType, status):
        for intf in self.interfaces:
            intf.send_acmp(commandResponse, messageType, status)

    def connectListener(self, response):
        """
        The connectListener function uses the passed in response structure to connect a stream to the ATDECC Listener.
        
        This function sets the fields of the ATDECC ListenerStreamInfos entry for the listener_unique_id 
        to the values of the equivalent fields in the response structure, 
        set the connected field to TRUE and initiates an SRP Listener registration.
        
        The connectListener function returns the response structure, with any updated flags. 
        The connectListener function also returns a status code as defined in Table 8­3 
        indicating either SUCCESS or the reason for a failure.
        """

        # we don't support SRP

        self.listenerStreamInfos[response.listener_unique_id] = struct_acmp_listener_stream_info(
            talker_entity_id = response.talker_entity_id,
            talker_unique_id = response.talker_unique_id,
            connected = True,
            stream_id = response.header.stream_id,
            stream_dest_mac = response.stream_dest_mac,
            controller_entity_id = response.controller_entity_id,
            flags = response.flags,
            stream_vlan_id = response.stream_vlan_id,
            pending_connection = False
        )

        # TODO are there any reasons for this to error out, i.e. return a different status?
        return [response, at.JDKSAVDECC_ACMP_STATUS_SUCCESS]

    def disconnectListener(self, command):
        """
        The disconnectListener function uses the passed in command structure 
        to disconnect the stream from an ATDECC Listener.
        
        This function initiates an SRP Talker de­registration and sets all fields of the 
        ATDECC ListenerStreamInfos entry for the listener_unique_id to zero (0) or FALSE.
        
        The disconnectListener function returns the command structure, with any updated flags. 
        The discon­ nectListener function also returns a status code as defined in Table 8­3 
        indicating either SUCCESS or the reason for a failure.
        """

        # we don't support SRP

        self.listenerStreamInfos[command.listener_unique_id] = struct_acmp_listener_stream_info(
            talker_entity_id = uint64_to_eui64(0),
            talker_unique_id = 0,
            connected = False,
            stream_id = uint64_to_eui64(0),
            stream_dest_mac = uint64_to_eui48(0),
            controller_entity_id = uint64_to_eui64(0),
            flags = 0,
            stream_vlan_id = 0,
            pending_connection = False
        )

        # TODO are there any reasons for this to error out, i.e. return a different status?
        return [command, at.JDKSAVDECC_ACMP_STATUS_SUCCESS]

    def cancelTimeout(self, commandResponse):
        """
        The cancelTimeout function stops the timeout timer of the inflight entry 
        associated with the commandResponse parameter. 
        The commandResponse may be a copy of the command entry within the inflight entry 
        or may be the response received for that command.
        """

        # assumption: "stops the timeout" means "sets the timout field in the inflight entry to zero"
        
        matching_inflight_index = self.findMatchingInflightIndex(commandResponse)

        if matching_inflight_index is not None:
            self.inflight[matching_inflight_index].timeout = 0

    def removeInflight(self, commandResponse):
        """
        The removeInflight function removes an entry from the inflight variable 
        associated with the commandResponse parameter. 
        The commandResponse may be a copy of the command entry within the inflight entry 
        or may be the response received for that command.
        """
        matching_inflight_index = self.findMatchingInflightIndex(commandResponse)

        if matching_inflight_index is not None:
            del self.inflight[matching_inflight_index]

    def getState(self, command):
        """
        The getState function returns a response structure of type ACMPCommandResponse 
        filled with the contents of the command parameter, with the stream_id, 
        stream_dest_mac, stream_vlan_id, connection_count, flags, talker_entity_id 
        and talker_unique_id fields set to the values for the ATDECC ListenerStreamInfos entry 
        associated with the stream identified by the command structure. 
        The getState function also returns a status code as defined in Table 8­3 
        indicating either SUCCESS or the reason for a failure.
        """

        listenerStreamInfo = self.listenerStreamInfos[command.listener_unique_id]

        response = at.struct_jdksavdecc_acmpdu(
            header = at.struct_jdksavdecc_acmpdu_common_control_header(
                message_type=at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_RESPONSE,
                stream_id=listenerStreamInfo.stream_id, 
            ),
            stream_dest_mac=listenerStreamInfo.stream_dest_mac,
            stream_vlan_id=listenerStreamInfo.stream_vlan_id,
            # In a GET_RX_STATE_RESPONSE message, the connection_count field is used to indicate whether the stream sink of the ATDECC Listener is connected or not.
            connection_count=(1 if listenerStreamInfo.connected else 0),
            flags=listenerStreamInfo.flags,
            talker_entity_id=listenerStreamInfo.talker_entity_id,
            talker_unique_id=listenerStreamInfo.talker_unique_id
        )
        
        # TODO are there any reasons for this to error out, i.e. return a different status?
        return [response, at.JDKSAVDECC_ACMP_STATUS_SUCCESS]

    def listenerIsAcquiredOrLockedByOther(self, commandResponse):
        """
        The listenerIsAcquiredOrLockedByOther function returns a Boolean 
        indicating if the stream has been acquired or locked for exclusive access by another ATDECC Controller.

        If the ATDECC Listener does not implement the ATDECC Entity Model 
        then this function result is based on similar functionality from the enumeration 
        and control protocol being used. If there is no enumeration and control protocol then this function returns FALSE.

        If the ATDECC Listener does implement the ATDECC Entity Model then this function returns TRUE 
        if the STREAM_INPUT representing this stream has been acquired by an ATDECC Controller 
        and the controller_entity_id field of the commandResponse does not match 
        the acquiring ATDECC Controller’s Entity ID or if the STREAM_INPUT representing this stream 
        has been locked by an ATDECC Controller and the controller_entity_id field of the commandResponse 
        does not match the acquiring ATDECC Controller’s Entity ID. Otherwise it returns FALSE.
        """

        # TODO we implement the Entity Model, hence option 2 applies
        # the issue is, we have no access to AEM from here, we need to inject it
        return False

    def findMatchingInflightIndex(self, commandResponse):
        return next((index for index, item in enumerate(self.inflight) if (
            eui64_to_uint64(item.command.controller_entity_id) == eui64_to_uint64(commandResponse.controller_entity_id) and
            eui64_to_uint64(item.command.talker_entity_id) == eui64_to_uint64(commandResponse.talker_entity_id) and
            item.command.talker_unique_id == commandResponse.talker_unique_id and
            eui64_to_uint64(item.command.listener_entity_id) == eui64_to_uint64(commandResponse.listener_entity_id) and
            item.command.listener_unique_id == commandResponse.listener_unique_id
        )), None)

    def run(self):
        logging.debug("ACMPListenerStateMachine: Starting thread")
        
        for intf in self.interfaces:
            intf.register_acmp_cb(self.acmp_cb)

        while True:
            self.rcvdConnectRXCmd = False
            self.rcvdDisconnectRXCmd = False
            self.rcvdConnectTXResp = False
            self.rcvdDisconnectTXResp = False
            self.rcvdGetRXState = False
            
            if self.rcvdCmdResp.empty():
                self.event.wait(1)
                # signalled
                self.event.clear()
                
            if self.doTerminate:
                break
                
            try:
                cmd = self.rcvdCmdResp.get_nowait()
                # TODO we have to convert to struct_acmp_inflight_command ?
                self.inflight.append(cmd)
            except Empty:
                pass
            
            try:
                # check timeouts
                ct = self.currentTime
                retried = []

                # self.inflight: list struct_jdksavdecc_acmpdu

                if len(self.inflight):
                    import pdb
                    pdb.set_trace()
                
                    while len(self.inflight) and ct >= self.inflight[0].timeout:
                        infl = self.inflight.pop(0)
                        if infl.command.message_type == at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND:
                            # CONNECT TX TIMEOUT
                            if infl.retried:
                                response = infl.command
                                response.sequence_id = infl.original_sequence_id
                                listenerInfo = self.listenerStreamInfos[rcvdCmdResp.listener_unique_id]
                                listenerInfo.pending_connection = False
                                self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, response, at.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)
                            else:
                                # Retry
                                self.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, infl.command, True)
                                infl.retried = True
                                retried.append(infl)
                        
                        elif infl.command.message_type == at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND:
                            # DISCONNECT TX TIMEOUT
                            if infl.retried:
                                response = infl.command
                                response.sequence_id = infl.original_sequence_id
                                self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, at.JDKSAVDECC_ACMP_STATUS_LISTENER_TALKER_TIMEOUT)
                            else:
                                self.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND, infl.command, True)
                                infl.retried = True
                                retried.append(infl)
                        
                # reinsert retries into inflights
                for infl in retried[::-1]:
                    self.inflight.insert(0, infl)
            
                if self.rcvdConnectRXCmd:
                    # CONNECT RX COMMAND
                    logging.debug("Received Connect RX command")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        if self.listenerIsAcquiredOrLockedByOther(self.rcvdCmdResp):
                            self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, self.rcvdCmdResp, at.JDKSAVDECC_ACMP_STATUS_CONTROLLER_NOT_AUTHORIZED)
                        elif self.listenerIsConnected(self.rcvdCmdResp):
                            self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, self.rcvdCmdResp, at.JDKSAVDECC_ACMP_STATUS_LISTENER_EXCLUSIVE)
                        else:
                            if self.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_TX_COMMAND, self.rcvdCmdResp, False):
                                listenerInfo = self.listenerStreamInfos[self.rcvdCmdResp.listener_unique_id]
                                listenerInfo.talker_entity_id = self.rcvdCmdResp.talker_entity_id
                                listenerInfo.talker_unique_id = self.rcvdCmdResp.talker_unique_id
                                listenerInfo.pending_connection = True
                    else:
                        self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, self.rcvdCmdResp, at.JDKSAVDECC_ACMP_STATUS_LISTENER_UNKNOWN_ID)

                    self.rcvdConnectRXCmd = False

                if self.rcvdConnectTXResp:
                    # CONNECT TX RESPONSE
                    logging.debug("Received Connect TX response")

                    if  self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        if self.rcvdCmdResp.status == at.JDKSAVDECC_ACMP_STATUS_SUCCESS:
                            response, status = self.connectListener(self.rcvdCmdResp)
                        else:
                            response, status = (self.rcvdCmdResp, self.rcvdCmdResp.status)
                        
                        listenerInfo = self.listenerStreamInfos[self.rcvdCmdResp.listener_unique_id]
                        listenerInfo.pending_connection = False
                    
                        import pdb
                        pdb.set_trace()
                        response.sequence_id = inflight[x].original_sequence_id # ????
                        self.cancelTimeout(self.rcvdCmdResp)
                        self.removeInflight(rcvdCmdResp) # ????
                        self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE, response, status)

                    self.rcvdConnectTXResp = False

                if self.rcvdGetRXState:
                    # GET STATE
                    logging.debug("Received Get State")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        response, error = self.getState(self.rcvdCmdResp)
                    else:
                        response, error = (self.rcvdCmdResp, at.JDKSAVDECC_ACMP_STATUS_LISTENER_UNKNOWN_ID)
                    
                    self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_RESPONSE, response, error)

                    self.rcvdGetRXState = False

                if self.rcvdDisconnectRXCmd:
                    # DISCONNECT RX COMMAND
                    logging.debug("Received Disconnect RX command")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        if self.listenerIsConnectedTo(self.rcvdCmdResp):
                            response, status = self.disconnectListener(self.rcvdCmdResp)
                            if status == at.JDKSAVDECC_ACMP_STATUS_SUCCESS:
                                self.txCommand(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_TX_COMMAND, self.rcvdCmdResp, False)
                            else:
                                self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, status)
                        else:
                            self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, self.rcvdCmdResp, at.JDKSAVDECC_ACMP_STATUS_NOT_CONNECTED)
                    else:
                        self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, self.rcvdCmdResp, at.JDKSAVDECC_ACMP_STATUS_LISTENER_UNKNOWN_ID)

                    self.rcvdDisconnectRXCmd = False

                if self.rcvdDisconnectTXResp:
                    # CONNECT TX RESPONSE
                    logging.debug("Received Disconnect TX response")

                    if self.validListenerUnique(self.rcvdCmdResp.listener_unique_id):
                        response, status = (self.rcvdCmdResp, self.rcvdCmdResp.status)

                        import pdb
                        pdb.set_trace()
                        response.sequence_id = inflight[x].original_sequence_id # ???
                        self.cancelTimeout(self.rcvdCmdResp)
                        self.removeInflight(self.rcvdCmdResp)  # ???
                        self.txResponse(at.JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE, response, status)

                    self.rcvdDisconnectTXResp = False
            except Exception as e:
                traceback.print_exc()
#                logging.error("Exception: %s", e)

        for intf in self.interfaces:
            intf.unregister_acmp_cb(self.acmp_cb)

        logging.debug("ACMPListenerStateMachine: Ending thread")
