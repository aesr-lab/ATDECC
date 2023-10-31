import pytest
from unittest.mock import patch, Mock
import time

from adp import EntityInfo, DiscoveryStateMachine, GlobalStateMachine
from util import *

class TestDiscoveryStateMachine:

    def test_have_entity(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42)

        assert not dsm.haveEntity(42)

        dsm.entities = {
            42: (ei, ei.valid_time)
        }

        assert dsm.haveEntity(42)

    def test_add_entity(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42)

        assert dsm.entities == {}

        dsm.addEntity(ei)

        entity_info, timeout = dsm.entities[42]
        assert entity_info == ei

    def test_update_entity(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42, entity_model_id=0)

        dsm.entities = {
            42: (ei, ei.valid_time)
        }

        old_entity_info, old_timeout = dsm.entities[42]

        assert old_entity_info.entity_model_id == 0

        ei.entity_model_id = 1
        dsm.updateEntity(ei)

        new_entity_info, new_timeout = dsm.entities[42]

        assert new_entity_info.entity_model_id == 1
        assert new_timeout > old_timeout
        
    def test_remove_entity(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42)

        dsm.entities = {
            42: (ei, ei.valid_time)
        }

        entity_id = uint64_to_eui64(42)
        dsm.removeEntity(entity_id)

        assert dsm.entities == {}

    def test_discover(self):
        dsm = DiscoveryStateMachine([])
        dsm.txDiscover = Mock()

        dsm.start()
        dsm.doDiscover = True
        dsm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)
        
        dsm.txDiscover.assert_called()

        dsm.performTerminate()
        dsm.join()

    def test_available_existing_entity(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42)

        dsm.entities = {
            42: (ei, GlobalStateMachine().currentTime+ei.valid_time)
        }

        dsm.rcvdEntityInfo = ei
        dsm.updateEntity = Mock()
        dsm.addEntity = Mock()

        dsm.start()
        dsm.rcvdAvailable = True
        dsm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        dsm.updateEntity.assert_called()
        dsm.addEntity.assert_not_called()

        dsm.performTerminate()
        dsm.join()

    def test_available_new_entity(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42)

        dsm.entities = {}

        dsm.rcvdEntityInfo = ei
        dsm.updateEntity = Mock()
        dsm.addEntity = Mock()

        dsm.start()
        dsm.rcvdAvailable = True
        dsm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        dsm.addEntity.assert_called()
        dsm.updateEntity.assert_not_called()

        dsm.performTerminate()
        dsm.join()

    def test_departing(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)

        dsm = DiscoveryStateMachine([])
        dsm.removeEntity = Mock()
        dsm.rcvdEntityInfo = ei

        dsm.start()
        dsm.rcvdDeparting = True
        dsm.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        dsm.removeEntity.assert_called()

        dsm.performTerminate()
        dsm.join()

    def test_timeout(self):
        dsm = DiscoveryStateMachine([])
        ei = EntityInfo(entity_id=42, entity_model_id=0)

        # we set the timeout to 0 to be immediately called
        dsm.entities = {
            42: (ei, 0)
        }

        dsm.removeEntity = Mock()

        dsm.start()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1.1)

        dsm.removeEntity.assert_called()
        dsm.performTerminate()
        dsm.join()
