import pytest
from unittest.mock import patch, Mock

from atdecc.adp import EntityInfo, AdvertisingEntityStateMachine
from atdecc import InterfaceStateMachine

class TestAdvertisingEntityStateMachine:

    def test_random_device_delay(self):
        with patch('atdecc.adp.EntityInfo') as MockedEntityInfo:
            # Set the `valid_time` attribute to return a specific value
            instance = MockedEntityInfo.return_value
            instance.valid_time = 62
            instance.entity_id = 0

            aesm = AdvertisingEntityStateMachine(EntityInfo(), [])

            for count in range(10):
                # should return a value between 0 and 1/5 of the valid time
                assert aesm.randomDeviceDelay() >= 0
                assert aesm.randomDeviceDelay() < 62 * 1000. / 5.

    def test_send_available(self):
        mock_ism = Mock()

        aesm = AdvertisingEntityStateMachine(EntityInfo(), [mock_ism])
        aesm.sendAvailable()

        mock_ism.performAdvertise.assert_called()

    def test_perform_advertise(self):
        # when waiting, advertise immediately
        with patch('atdecc.adp.AdvertisingEntityStateMachine.randomDeviceDelay') as MockedDeviceDelay:
            # we stub the random device delay to 0 so the DELAY phase is skipped
            MockedDeviceDelay.return_value = 0

            aesm = AdvertisingEntityStateMachine(EntityInfo(), [])
            aesm.sendAvailable = Mock()

            aesm.start()
            aesm.needsAdvertise = True
            aesm.event.set()

            aesm.sendAvailable.assert_called()

            aesm.performTerminate()
            aesm.join()

    def test_reset_available_index(self):
        # initializing resets available index of entity to 0
        entity_info = EntityInfo()
        entity_info.available_index = 1

        aesm = AdvertisingEntityStateMachine(entity_info, [])

        aesm.start()
        aesm.performTerminate()
        aesm.join()

        assert entity_info.available_index == 0
