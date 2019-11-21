import os

import pytest
from components.memorycontroller import MemoryController


@pytest.fixture(scope='session', autouse=True)
def set_debugging_environ():
    os.environ['ASS2_DEBUGGING'] = 'true'


@pytest.fixture
def mc():
    return MemoryController()
