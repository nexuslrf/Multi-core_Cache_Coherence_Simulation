import pytest

from components.mesibus import Bus
from components.mesicachecontroller import MesiCacheController


@pytest.fixture
def cache_0():
    cache = MesiCacheController('P0')
    return cache


@pytest.fixture
def cache_1():
    cache = MesiCacheController('P1')
    return cache


@pytest.fixture
def cache_assoc_4():
    cache = MesiCacheController('P1', assoc=4)
    return cache


@pytest.fixture
def bus():
    mesi_bus = Bus()
    return mesi_bus
