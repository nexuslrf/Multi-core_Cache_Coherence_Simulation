import pytest

from components.cachebase import CacheBase


@pytest.mark.parametrize(
    "tag, index, offset, expected_address",
    [
        (5, 1, 0, 0b1010000100000)
    ]
)
def test_get_address_from_pieces(tag, index, offset, expected_address):
    cache = CacheBase('P1', assoc=4)
    address = cache.get_address_from_pieces(tag, index, offset)
    assert address ==expected_address
