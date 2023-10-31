import pytest
import time

from adp import GlobalStateMachine

class TestGlobalStateMachine:

    def test_returns_current_time(self):
        before = GlobalStateMachine().currentTime
        time.sleep(0.1)
        after = GlobalStateMachine().currentTime

        assert before != after
