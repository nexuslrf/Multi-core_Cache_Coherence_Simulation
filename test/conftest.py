import pytest
from components.memorycontroller import MemoryController


@pytest.fixture
def mc():
    return MemoryController()
