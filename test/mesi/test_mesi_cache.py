import pytest

from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.mesi import *
from job import Job
from mesibus import Bus
from mesicachecontroller import MesiCacheController


def test_get_cache_block(cache_0:MesiCacheController):
    cache_0.data[0][1] = [0b101, INVALID, UNLOCKED]

    block = cache_0.get_cache_block(0b10100000000100)

    assert block is not None
    assert list(block) == [0b101, INVALID, UNLOCKED]


def test_simple_read_hit(cache_0:MesiCacheController):
    cache_0.data[0] = [0, SHARED, UNLOCKED]
    job = Job(LOAD, 0b1)
    cache_0.schedule_job(job)
    cache_0.interim()
    assert cache_0.current_job.status_in_cache == HITTING
    cache_0.tick()
    assert cache_0.current_job is None


def test_simple_access_history_update(cache_0:MesiCacheController):
    cache_0.data[0] = [0, SHARED, UNLOCKED]
    job = Job(LOAD, 0b1)
    cache_0.schedule_job(job)
    cache_0.interim()
    assert cache_0.current_job.status_in_cache == HITTING
    assert list(cache_0.access_history[0]) == [0]
    cache_0.tick()
    assert cache_0.current_job is None


def test_simple_read_from_bus_then_hit(cache_0: MesiCacheController, cache_1: MesiCacheController, bus:Bus):
    bus.connected_caches = [cache_0, cache_1]
    cache_0.bus = bus
    cache_1.bus = bus

    cache_1.data[0] = [0, SHARED, UNLOCKED]
    job = Job(LOAD, 0b1)
    cache_0.schedule_job(job)
    cache_0.interim()
    cache_1.interim()
    assert bus.bus_master is None
    bus.interim()
    assert bus.bus_master == cache_0
    assert cache_0.current_job.status_in_cache == RECEIVING_FROM_BUS
    for _ in range(16):
        cache_0.tick()
        cache_1.tick()
    assert bus.bus_master is None
    assert cache_0.current_job.status_in_cache == HITTING
