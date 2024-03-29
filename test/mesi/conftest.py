import pytest

from components.mesibus import Bus
from components.mesicache import MesiCache


@pytest.fixture
def cache_0():
    cache = MesiCache('P0')
    return cache


@pytest.fixture
def cache_1():
    cache = MesiCache('P1')
    return cache


@pytest.fixture
def cache_assoc_4():
    cache = MesiCache('P1', assoc=4)
    return cache


@pytest.fixture
def bus():
    mesi_bus = Bus()
    return mesi_bus
