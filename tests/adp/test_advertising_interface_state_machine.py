import pytest
from unittest.mock import patch, Mock
import time

from adp import EntityInfo, InterfaceStateMachine
from util import *

class TestAdvertisingInterfaceStateMachine:
    def test_departing(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        aism = InterfaceStateMachine(ei, [])
        aism.txEntityDeparting = Mock()

        aism.start()
        assert aism.is_alive()

        aism.doTerminate = True
        aism.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        assert not aism.is_alive()
        aism.txEntityDeparting.assert_called()

    def test_advertise(self):
        ei = EntityInfo(entity_id=42, entity_model_id=0)
        aism = InterfaceStateMachine(ei, [])
        aism.txEntityAvailable = Mock()

        aism.start()
        
        aism.doAdvertise = True
        aism.event.set()

        # this is an antipattern, have to research time travel functionality in pytest
        time.sleep(1)

        aism.txEntityAvailable.assert_called()
        assert not aism.doAdvertise

        aism.performTerminate()
