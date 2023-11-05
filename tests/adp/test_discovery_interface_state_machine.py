import pytest
from unittest.mock import patch, Mock
import time

from adp import EntityInfo, InterfaceStateMachine
from util import *

class TestDiscoveryInterfaceStateMachine:
    def test_discover_matching_entity_id(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        dism = InterfaceStateMachine(ei, [])
        dism.lastLinkIsUp = True # to avoid advertising when link goes up
        dism.advertisedConfigurationIndex = 0 # to avoid advertising when config changes
        dism.performAdvertise = Mock()

        dism.start()

        # "stubbed" callback call from interface
        dism.adp_cb(
            at.struct_jdksavdecc_adpdu(
                header = at.struct_jdksavdecc_adpdu_common_control_header(
                    message_type=at.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER,
                    valid_time=31,
                    entity_id=uint64_to_eui64(42),
                )
            )
        )
        dism.event.set()
        
        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        dism.performAdvertise.assert_called_once()

        dism.performTerminate()

    def test_discover_entity_id_0(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        dism = InterfaceStateMachine(ei, [])
        dism.lastLinkIsUp = True # to avoid advertising when link goes up
        dism.advertisedConfigurationIndex = 0 # to avoid advertising when config changes
        dism.performAdvertise = Mock()

        dism.start()

        # "stubbed" callback call from interface
        dism.adp_cb(
            at.struct_jdksavdecc_adpdu(
                header = at.struct_jdksavdecc_adpdu_common_control_header(
                    message_type=at.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER,
                    valid_time=31,
                    entity_id=uint64_to_eui64(0),
                )
            )
        )

        dism.event.set()
        
        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        dism.performAdvertise.assert_called_once()

        dism.performTerminate()

    def test_discover_not_matching_entity_id(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        dism = InterfaceStateMachine(ei, [])
        dism.lastLinkIsUp = True # to avoid advertising when link goes up
        dism.advertisedConfigurationIndex = 0 # to avoid advertising when config changes
        dism.performAdvertise = Mock()

        dism.start()

        # "stubbed" callback call from interface
        dism.adp_cb(
            at.struct_jdksavdecc_adpdu(
                header = at.struct_jdksavdecc_adpdu_common_control_header(
                    message_type=at.JDKSAVDECC_ADP_MESSAGE_TYPE_ENTITY_DISCOVER,
                    valid_time=31,
                    entity_id=uint64_to_eui64(41),
                )
            )
        )

        dism.event.set()
        
        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        dism.performAdvertise.assert_not_called()

        dism.performTerminate()

    def test_update_gm(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        dism = InterfaceStateMachine(ei, [])
        dism.currentGrandmasterID = 0
        dism.advertisedGrandmasterID = 0
        dism.performAdvertise = Mock()

        dism.start()

        dism.currentGrandmasterID = 1
        dism.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        assert dism.advertisedGrandmasterID == 1
        dism.performAdvertise.assert_called()

        dism.performTerminate()
    
    def test_update_config(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        dism = InterfaceStateMachine(ei, [])
        dism.currentConfigurationIndex = 0
        dism.advertisedConfigurationIndex = 0
        dism.performAdvertise = Mock()

        dism.start()

        dism.currentConfigurationIndex = 1
        dism.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        assert dism.advertisedConfigurationIndex == 1
        dism.performAdvertise.assert_called()

        dism.performTerminate()

    def test_link_state_change(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        dism = InterfaceStateMachine(ei, [])
        dism.linkIsUp = True
        dism.lastLinkIsUp = True

        dism.performAdvertise = Mock()

        dism.start()

        dism.linkIsUp = False
        dism.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        assert dism.lastLinkIsUp == False
        dism.performAdvertise.assert_called()

        dism.performTerminate()
