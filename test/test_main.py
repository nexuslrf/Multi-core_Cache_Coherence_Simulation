from mesicachecontroller import MesiCacheController
from util import resolve_memory_address
import pytest


@pytest.mark.parametrize("address, expected", [
    (0x8, (0, 1, 0)),
    (0b10011010, (9, 1, 2))
])
def test_memory_resolution(address, expected):
    result = resolve_memory_address(address, 0b1000, 0b111, 1, 3)
    assert result == expected


def test_cache_controller_init():
    cache = MesiCacheController('P1', 4096, 2, 32)
    assert cache.set_index_mask == 0b11111100000
    assert cache.offset_mask == 0b11111
    assert cache.m == 6
    assert cache.n == 5
