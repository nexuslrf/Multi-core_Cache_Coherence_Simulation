import pytest

from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.mesi import *
from job import Job, CacheJob
from main import Simulator
from components.mesibus import Bus
from components.mesicache import MesiCache
import numpy as np

from opstream import FakeOpStream


def test_get_cache_block(cache_0: MesiCache):
    cache_0.data[0][1] = [0b101, INVALID, UNLOCKED]

    block = cache_0.get_cache_block(0b10100000000100)

    assert block is None

    cache_0.data[0][1] = [0b101, SHARED, UNLOCKED]

    block = cache_0.get_cache_block(0b10100000000100)

    assert block is not None
    assert list(block) == [0b101, SHARED, UNLOCKED]


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
def test_simple_cache_set_order_update(cache_assoc_4: MesiCache, cache_set_array, expected):
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
def test_cache_set_order_update_raise_error_if_tag_not_found(cache_assoc_4: MesiCache,
                                                             cache_set_array):
    with pytest.raises(LookupError):
        cache_assoc_4.data[1] = np.matrix(cache_set_array)
        assert cache_assoc_4.update_cache_set_access_order(1, 55)


@pytest.mark.parametrize(
    "cache_set_array, expected",
    [
        ([[11, 1, 0],
          [22, 0, 0],
          [33, 1, 0],
          [44, 1, 0]],
         [[11, 1, 0],
          [1, 0, WRITE_LOCKED],
          [33, 1, 0],
          [44, 1, 0]]
         ),
        ([[11, 1, 0],
          [22, 1, 0],
          [33, 1, 0],
          [44, 1, 0]],
         [[11, 1, 0],
          [22, 1, 0],
          [33, 1, 0],
          [1, 0, WRITE_LOCKED]]
         )
    ]
)
def test_reserve_space_for_block(cache_assoc_4: MesiCache, cache_set_array, expected, mc):
    cache_assoc_4.memory_controller = mc
    cache_assoc_4.data[1] = np.matrix(cache_set_array)
    address = cache_assoc_4.get_address_from_pieces(1, 1, 1)
    cache_assoc_4.current_job = CacheJob(LOAD, address=address, remaining_cycles=10)
    cache_assoc_4.reserve_space_for_incoming_block(address)
    assert np.array_equal(cache_assoc_4.data[1], expected)


def test_simple_read_from_bus_then_hit(cache_0: MesiCache, cache_1: MesiCache, bus: Bus):
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


def test_cache_direct_hit_only():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b100000100111), (0, 0b1000000110011)]
    simulator = Simulator(data=None, num_cores=1)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[0].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.run()
    assert simulator.procs[0].cache.total_access_count == len(op_list)
    assert simulator.procs[0].cache.cache_miss_count == 0
    assert simulator.counter == len(op_list)
    assert np.array_equal(simulator.procs[0].cache.data[1], [
        [2, 1, 0],
        [1, 1, 0]
    ])


def test_cache_fetch_from_memory_only():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    op_list1 = [(0, 0b100001100001), (0, 0b1000001110000), (0, 0b1100001100111), (0, 0b10000001110011)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    assert simulator.procs[0].cache.total_access_count == len(op_list)
    assert simulator.procs[0].cache.cache_miss_count == 4
    assert simulator.counter == len(op_list) * 101 + 1  # the extra 1 cycle is spent competing for bus ownership


@pytest.mark.parametrize(
    "cache_set_array, number_of_mem_access, dest_block_states",
    [
        ([[11, SHARED, 0],
          [22, SHARED, 0]], 0, [SHARED, SHARED]
         ),
        ([[11, SHARED, 0],
          [33, SHARED, 0]], 1, [EXCLUSIVE, SHARED]
         ),
        ([[11, SHARED, 0],
          [22, INVALID, 0]], 1, [EXCLUSIVE, SHARED]
         ),
        ([[11, MODIFIED, 0],
          [22, EXCLUSIVE, 0]], 0, [SHARED, SHARED]
         )
    ]
)
def test_cache_fetch_from_bus_only(cache_set_array, number_of_mem_access, dest_block_states):
    op_list_raw = [(0, 11, 1, 1), (0, 22, 1, 1)]
    op_list1 = []
    simulator = Simulator(data=None, num_cores=2)
    op_list = [(x[0], simulator.procs[0].cache.get_address_from_pieces(*x[1:])) for x in op_list_raw]

    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.procs[1].cache.data[1] = np.matrix(cache_set_array)
    simulator.run()
    assert simulator.procs[0].cache.total_access_count == len(op_list)
    assert simulator.procs[0].cache.cache_miss_count == number_of_mem_access
    assert np.array_equal(simulator.procs[0].cache.data[1][:, 1], dest_block_states)
    assert simulator.counter == (len(op_list) - number_of_mem_access) * (
                2 * simulator.procs[0].cache.block_size // 4 + 1) + number_of_mem_access * 101


def dummy_callback(result):
    return


def test_cache_compete_for_bus_ownership(cache_0, cache_1, bus):
    cache_0.bus = bus
    cache_1.bus = bus
    bus.connected_caches = [cache_0, cache_1]
    cache_0.bus.apply_for_bus_master(cache_0, dummy_callback)
    cache_1.bus.apply_for_bus_master(cache_1, dummy_callback)
    assert bus.bus_master is None
    bus.interim()
    assert bus.bus_master == cache_0


def test_cache_read_block_while_other_cache_fetching_same_block_from_mem():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    op_list1 = [(2, 10), (0, 0b100000100001)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    assert simulator.procs[1].counter == 100 + simulator.procs[1].cache.block_size // 4 * 2 + 1
    assert simulator.counter == 100 + simulator.procs[1].cache.block_size // 4 * 2 + (len(op_list) - 1) * 101


def test_cache_read_four_core_same_access():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list)
    simulator.procs[2].op_stream = FakeOpStream(op_list)
    simulator.procs[3].op_stream = FakeOpStream(op_list)
    simulator.run()


def test_cache_store_direct_hit():
    op_list = [(1, 0b100000100001), (1, 0b1000000110000), (1, 0b100000100111), (1, 0b1000000110011)]
    simulator = Simulator(data=None, num_cores=1)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[0].cache.data[1] = np.matrix([
        [1, EXCLUSIVE, 0],
        [2, MODIFIED, 0]
    ])
    simulator.run()
    assert simulator.counter == len(op_list)
    assert np.all(simulator.procs[0].cache.data[1][:, 1] == MODIFIED)


def test_cache_store_fetch_from_memory_only():
    op_list = [(1, 0b100000100001), (1, 0b1000000110000), (1, 0b1100000100111), (1, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=1)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.run()
    assert simulator.counter == len(op_list) * 101 + 200


@pytest.mark.parametrize(
    "cache_set_array, number_of_mem_access, dest_block_states",
    [
        ([[11, SHARED, 0],
          [22, SHARED, 0]], 0, [INVALID, INVALID]
         ),
        ([[11, SHARED, 0],
          [33, SHARED, 0]], 1, [INVALID, SHARED]
         ),
        ([[11, SHARED, 0],
          [22, INVALID, 0]], 1, [INVALID, INVALID]
         ),
        ([[11, MODIFIED, 0],
          [22, EXCLUSIVE, 0]], 0, [INVALID, INVALID]
         )
    ]
)
def test_cache_store_hit_from_bus_or_mem(cache_set_array, number_of_mem_access, dest_block_states):
    op_list_raw = [(1, 11, 1, 1), (1, 22, 1, 1)]
    op_list1 = []
    simulator = Simulator(data=None, num_cores=2)
    op_list = [(x[0], simulator.procs[0].cache.get_address_from_pieces(*x[1:])) for x in op_list_raw]

    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.procs[1].cache.data[1] = np.matrix(cache_set_array)
    simulator.run()
    assert np.array_equal(simulator.procs[1].cache.data[1][:, 1], dest_block_states)
    assert simulator.counter == (len(op_list) - number_of_mem_access) * (
                simulator.procs[0].cache.block_size // 4 * 2 + 1) + number_of_mem_access * 101


def test_cache_write_block_while_other_cache_fetching_same_block_from_mem():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    op_list1 = [(2, 10), (1, 0b100000100001)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    assert simulator.procs[1].counter == 100 + simulator.procs[1].cache.block_size // 4 * 2 + 2
    assert simulator.counter == 101 + simulator.procs[1].cache.block_size // 4 * 2 + (len(op_list) - 1) * 101
    assert simulator.procs[0].total_load_instructions == 4
    assert simulator.procs[0].total_store_instructions == 0
    assert simulator.procs[1].total_load_instructions == 0
    assert simulator.procs[1].total_store_instructions == 1


def test_interleaving_cache_write_from_different_caches():
    op_list = [(0, 0b100000100001), (1, 0b100000100001)]
    op_list1 = [(2, 10), (1, 0b100000100001)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    assert simulator.procs[1].counter == 101 + simulator.procs[1].cache.block_size // 4 * 2 + 2
    assert simulator.procs[1].total_compute_cycles == 10


def test_incoming_read_x_wait_for_local_read():
    op_list = [(1, 0b100000100001)]
    op_list1 = [(0, 0b100000100001)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.procs[0].cache.data[1] = np.matrix([
        [0, 0, 0],
        [0, 0, 0]
    ])
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, EXCLUSIVE, 0],
        [0, 0, 0]
    ])
    simulator.run()
    assert simulator.counter == 18
    assert simulator.procs[0].counter == 18
    assert simulator.procs[1].counter == 1


def test_cache_write_four_core_same_access():
    op_list = [(1, 0b100000100001), (1, 0b1000000110000), (1, 0b1100000100111), (1, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list)
    simulator.procs[2].op_stream = FakeOpStream(op_list)
    simulator.procs[3].op_stream = FakeOpStream(op_list)
    simulator.run()


def test_correctness_of_total_bus_traffic_counting():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    op_list1 = [(2, 10), (0, 0b100000100001)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    cache0 = simulator.procs[0].cache
    assert simulator.bus.total_bus_traffic == cache0.block_size * 1


def test_correctness_of_bus_invalidation_update_counting():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    op_list1 = [(2, 10), (1, 0b100000100001)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    assert simulator.bus.total_bus_invalidation_or_updates == 1


def test_counting_total_private_accesses():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    op_list1 = [(2, 10), (1, 0b100000100001), (0, 0b1000000110000)]
    simulator = Simulator(data=None, num_cores=2)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.run()
    cache0 = simulator.procs[0].cache
    cache1 = simulator.procs[1].cache
    assert cache0.total_private_accesses == 4
    assert cache1.total_private_accesses == 1
    assert cache1.total_access_count == 2


@pytest.mark.parametrize(
    "home_array, remote_array, home_array_after",
    [
        ([[11, SHARED, 0],
          [22, SHARED, 0]],
         [[11, SHARED, 0],
          [22, SHARED, 0]],
         [[11, MODIFIED, 0],
          [22, SHARED, 0]]
         )
    ]
)
def test_bus_read_x_to_full_cacheset_does_not_evict_block_if_block_present(home_array, remote_array, home_array_after):
    op_list_raw = [(1, 11, 1, 1)]
    op_list1 = []
    simulator = Simulator(data=None, num_cores=2)
    op_list = [(x[0], simulator.procs[0].cache.get_address_from_pieces(*x[1:])) for x in op_list_raw]

    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.procs[0].cache.data[1] = np.matrix(home_array)
    simulator.procs[1].cache.data[1] = np.matrix(remote_array)
    simulator.run()
    assert np.array_equal(simulator.procs[0].cache.data[1], home_array_after)


@pytest.mark.parametrize(
    "home_array, remote_array, home_array_after",
    [
        ([[11, SHARED, 0],
          [22, SHARED, 0]],
         [[11, INVALID, 0],
          [22, INVALID, 0]],
         [[11, MODIFIED, 0],
          [22, SHARED, 0]]
         )
    ]
)
def test_another(home_array, remote_array, home_array_after):
    op_list_raw = [(1, 11, 1, 1)]
    op_list1 = []
    simulator = Simulator(data=None, num_cores=2)
    op_list = [(x[0], simulator.procs[0].cache.get_address_from_pieces(*x[1:])) for x in op_list_raw]

    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].op_stream = FakeOpStream(op_list1)
    simulator.procs[0].cache.data[1] = np.matrix(home_array)
    simulator.procs[1].cache.data[1] = np.matrix(remote_array)
    simulator.run()
    assert np.array_equal(simulator.procs[0].cache.data[1], home_array_after)
    assert simulator.procs[0].counter == 1
