import pytest

from mesibus import Bus
from mesicachecontroller import MesiCacheController


@pytest.fixture
def cache_0():
    cache = MesiCacheController('P0')
    return cache


@pytest.fixture
def cache_1():
    cache = MesiCacheController('P1')
    return cache


@pytest.fixture
def bus():
    mesi_bus = Bus()
    return mesi_bus
