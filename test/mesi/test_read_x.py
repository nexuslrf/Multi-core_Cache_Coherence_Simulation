import numpy as np
import pytest

from constants.locking import *
from constants.mesi import *
from main import Simulator
from opstream import FakeOpStream


def test_all_other_3_with_shared_block():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[2].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[3].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.bus.bus_master = simulator.procs[0].cache
    result, payload = simulator.bus.send_read_X_req(simulator.procs[0].cache, 0b100000100001)
    assert result
    assert payload > 0
    assert np.array_equal(simulator.procs[1].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[2].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[3].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])


def test_only_1_with_shared_block():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[2].cache.data[1] = np.matrix([
        [3, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[3].cache.data[1] = np.matrix([
        [3, 1, 0],
        [2, 1, 0]
    ])
    simulator.bus.bus_master = simulator.procs[0].cache
    result, payload = simulator.bus.send_read_X_req(simulator.procs[0].cache, 0b100000100001)
    assert result
    assert payload > 0
    assert np.array_equal(simulator.procs[1].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[2].cache.data[1], [
        [3, 1, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[3].cache.data[1], [
        [3, 1, 0],
        [2, 1, 0]
    ])


def test_only_1_with_exclusive_block():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, EXCLUSIVE, 0],
        [2, 1, 0]
    ])
    simulator.procs[2].cache.data[1] = np.matrix([
        [3, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[3].cache.data[1] = np.matrix([
        [3, 1, 0],
        [2, 1, 0]
    ])
    simulator.bus.bus_master = simulator.procs[0].cache
    result, payload = simulator.bus.send_read_X_req(simulator.procs[0].cache, 0b100000100001)
    assert result
    assert payload > 0
    assert np.array_equal(simulator.procs[1].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[2].cache.data[1], [
        [3, 1, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[3].cache.data[1], [
        [3, 1, 0],
        [2, 1, 0]
    ])


def test_only_1_with_modified_block():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, MODIFIED, 0],
        [2, 1, 0]
    ])
    simulator.procs[2].cache.data[1] = np.matrix([
        [3, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[3].cache.data[1] = np.matrix([
        [3, 1, 0],
        [2, 1, 0]
    ])
    simulator.bus.bus_master = simulator.procs[0].cache
    result, payload = simulator.bus.send_read_X_req(simulator.procs[0].cache, 0b100000100001)
    assert result
    assert payload > 0
    assert np.array_equal(simulator.procs[1].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[2].cache.data[1], [
        [3, 1, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[3].cache.data[1], [
        [3, 1, 0],
        [2, 1, 0]
    ])


@pytest.mark.parametrize(
    'lock_type',[READ_LOCKED, WRITE_LOCKED]
)
def test_1_of_3_locked(lock_type):
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.procs[2].cache.data[1] = np.matrix([
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    simulator.procs[3].cache.data[1] = np.matrix([
        [1, 1, 0],
        [2, 1, 0]
    ])
    simulator.bus.bus_master = simulator.procs[0].cache
    result, payload = simulator.bus.send_read_X_req(simulator.procs[0].cache, 0b100000100001)
    assert not result
    assert payload > 0
    assert np.array_equal(simulator.procs[1].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[2].cache.data[1], [
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[3].cache.data[1], [
        [1, INVALID, 0],
        [2, 1, 0]
    ])


@pytest.mark.parametrize(
    'lock_type', [READ_LOCKED]
)
def test_3_of_3_locked(lock_type):
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b1100000100111), (0, 0b10000000110011)]
    simulator = Simulator(data=None, num_cores=4)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[1].cache.data[1] = np.matrix([
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    simulator.procs[2].cache.data[1] = np.matrix([
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    simulator.procs[3].cache.data[1] = np.matrix([
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    simulator.bus.bus_master = simulator.procs[0].cache
    result, payload = simulator.bus.send_read_X_req(simulator.procs[0].cache, 0b100000100001)
    assert not result
    assert payload == 0
    assert np.array_equal(simulator.procs[1].cache.data[1], [
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[2].cache.data[1], [
        [1, 1, lock_type],
        [2, 1, 0]
    ])
    assert np.array_equal(simulator.procs[3].cache.data[1], [
        [1, 1, lock_type],
        [2, 1, 0]
    ])
