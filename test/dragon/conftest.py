import pytest

from components.mesibus import Bus
from components.dragoncache import DragonCache


@pytest.fixture
def cache_0():
    cache = DragonCache('P0')
    return cache


@pytest.fixture
def cache_1():
    cache = DragonCache('P1')
    return cache


@pytest.fixture
def cache_assoc_4():
    cache = DragonCache('P1', assoc=4)
    return cache


@pytest.fixture
def bus():
    mesi_bus = Bus()
    return mesi_bus
