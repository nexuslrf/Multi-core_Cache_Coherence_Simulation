import numpy as np

import pytest

from components.cachebase import CacheBase
from constants.jobtype import *
from constants.mesi import *
from job import CacheJob


@pytest.mark.parametrize(
    "tag, index, offset, expected_address",
    [
        (5, 1, 0, 0b1010000100000)
    ]
)
def test_get_address_from_pieces(tag, index, offset, expected_address):
    cache = CacheBase('P1', assoc=4)
    address = cache.get_address_from_pieces(tag, index, offset)
    assert address == expected_address


@pytest.mark.parametrize(
    "existing_cache_set, incoming_tag, expected",
    [
        ([[1, SHARED, 0], [2, SHARED, 0]], 1, False),
        ([[1, INVALID, 0], [2, SHARED, 0]], 1, False),
        ([[2, SHARED, 0], [3, MODIFIED, 0]], 1, True),
        ([[6, INVALID, 0], [3, MODIFIED, 0]], 1, False),
        ([[6, EXCLUSIVE, 0], [3, MODIFIED, 0]], 1, True),
    ]
)
def test_reserve_space_for_incoming_block(existing_cache_set, incoming_tag, expected, mc):
    cache = CacheBase('P0')
    cache.data[1] = np.matrix(existing_cache_set)
    cache.memory_controller = mc
    address = cache.get_address_from_pieces(incoming_tag, 1, 0)
    cache.current_job = CacheJob(LOAD, address=address, remaining_cycles=10)
    assert expected == cache.reserve_space_for_incoming_block(address)
