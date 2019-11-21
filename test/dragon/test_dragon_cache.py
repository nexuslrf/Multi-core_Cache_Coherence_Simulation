import pytest

from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.dragon import *
from job import Job
from main import Simulator
from components.mesibus import Bus
from components.dragoncache import DragonCache
import numpy as np

from opstream import FakeOpStream


def test_get_cache_block(cache_0:DragonCache):
    cache_0.data[0][1] = [0b101, INVALID, UNLOCKED]

    block = cache_0.get_cache_block(0b10100000000100)

    assert block is not None
    assert list(block) == [0b101, INVALID, UNLOCKED]


@pytest.mark.parametrize(
    "cache_set_array, expected",
    [
        ([[11, 1, 0],
          [22, 1, 0],
          [33, 1, 0],
          [44, 1, 0]],

         [[44, 1, 0],
          [11, 1, 0],
          [22, 1, 0],
          [33, 1, 0]]
         ),
        ([[11, 1, 0],
          [33, 1, 0],
          [22, 1, 0],
          [44, 1, 0]
          ],

         [[44, 1, 0],
          [11, 1, 0],
          [33, 1, 0],
          [22, 1, 0]]
         )
    ]
)
def test_simple_cache_set_order_update(cache_assoc_4:DragonCache, cache_set_array, expected):
    cache_assoc_4.data[1] = np.matrix(cache_set_array)
    cache_assoc_4.update_cache_set_access_order(1, 44)
    assert np.array_equal(cache_assoc_4.data[1], expected)


@pytest.mark.parametrize(
    "cache_set_array",
    [
        ([[11, 1, 0],
          [22, 1, 0],
          [33, 1, 0],
          [44, 1, 0]]
         )
    ]
)
def test_cache_set_order_update_raise_error_if_tag_not_found(cache_assoc_4:DragonCache,
                                                             cache_set_array):
    with pytest.raises(LookupError):
        cache_assoc_4.data[1] = np.matrix(cache_set_array)
        assert cache_assoc_4.update_cache_set_access_order(1, 55)


def test_cache_direct_hit_only():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b100000100111), (0, 0b1000000110011)]
    simulator = Simulator(protocol='dragon', data=None, num_cores=1)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[0].cache.data[1] = np.matrix([
        [1, SC, 0],
        [2, SC, 0]
    ])
    simulator.run()
    assert simulator.counter == len(op_list)


def test_cache_compete_for_bus_ownership(cache_0, cache_1, bus):
    cache_0.bus = bus
    cache_1.bus = bus
    bus.connected_caches = [cache_0, cache_1]


def test_simple_read_from_bus_then_hit(cache_0: DragonCache, cache_1: DragonCache, bus:Bus):
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