import pytest

from adp import EntityInfo

VALID_TIME_MIN = 2
VALID_TIME_MAX = 62
TOO_SHORT_TIME = 0
TOO_LONG_TIME = 100

class TestEntityInfo:
    def test_valid_time_boundaries(self):
        entity = EntityInfo(valid_time=TOO_SHORT_TIME)
        assert entity.get_adpdu().header.valid_time == VALID_TIME_MIN // 2

        entity = EntityInfo(valid_time=TOO_LONG_TIME)
        assert entity.get_adpdu().header.valid_time == VALID_TIME_MAX // 2
