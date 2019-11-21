from math import log

import numpy as np

from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.mesi import *
from job import CacheJob
from util import resolve_memory_address


class CacheBase:
    def __init__(self, name, size=4096, assoc=2, block_size=32, memory_controller=None, bus=None):
        self.name = name
        self.current_job = None
        self.size = size
        self.assoc = assoc
        self.block_size = block_size
        self.n = int(log(block_size, 2))
        self.m = int(log(size / assoc / block_size, 2))
        self.set_index_mask = 0
        for _ in range(self.m):
            self.set_index_mask = (self.set_index_mask << 1) | 0b1
        for _ in range(self.n):
            self.set_index_mask = self.set_index_mask << 1
        self.offset_mask = 0
        for _ in range(self.n):
            self.offset_mask = (self.offset_mask << 1) | 0b1
        self.data = np.zeros((size // assoc // block_size, assoc, 3), dtype=int)
        self.memory_controller = memory_controller
        self.bus = bus

        self.job = None

    def is_busy(self):
        return self.current_job is not None

    def tick(self):
        if self.current_job is None:
            return
        else:
            if self.current_job.status_in_cache == RECEIVING_FROM_BUS:
                self.current_job.remaining_bus_read_cycles -= 1
                if self.current_job.remaining_bus_read_cycles < 1:
                    self.on_bus_read_finished()
                return

            if self.current_job.status_in_cache == HITTING:
                self.on_hit_finished()
                return

    def schedule_job(self, job):
        self.current_job = CacheJob.create_from_job(job, self.n)

    def interim(self):
        # run interim stuff if there is a current job
        raise NotImplementedError

    def get_cache_block(self, address):
        """
        get the cache block that contains the address, note that blocks in Invalid state will also be returned. As
        long as tag and index has a match.
        :param address: 32-bit memory address
        :return: None if block containing this address is not found in cache, otherwise the found block
        """
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                return block

        return None

    def lock_block(self, address, lock=READ_LOCKED):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[2] = lock
                return

        raise LookupError("[lock_block] block not found in cache")

    def unlock_block(self, address):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[2] = UNLOCKED

    def start_hitting(self):
        tag, set_index, _ = self.resolve_memory_address(self.current_job.address)
        self.update_cache_set_access_order(set_index, tag)

        self.current_job.status_in_cache = HITTING

    def on_hit_finished(self):
        self.unlock_block(self.current_job.address)
        self.current_job = None

    def on_fetch_from_memory_finished(self):
        self.start_hitting()

    def resolve_memory_address(self, address):
        return resolve_memory_address(address, self.set_index_mask, self.offset_mask, self.m, self.n)

    def update_cache_set_access_order(self, cache_set_index, block_tag):
        """
        Reorder a cache set by bringing the latest accessed block to the front, and shift the rest back.
        :param cache_set_index: index of the cache set
        :param block_tag: tag number of the latest accessed block
        :return: None
        """
        cache_set = self.data[cache_set_index]
        target_index = -1
        current_order = list(range(len(cache_set)))
        for i in current_order:
            if cache_set[i][1] != INVALID and cache_set[i][0] == block_tag:
                target_index = i
        if target_index < 0:
            raise LookupError("block with tag {} does not exist in the cache set!".format(block_tag))
        new_order = current_order.copy()
        new_order.remove(target_index)
        new_order.insert(0, target_index)
        cache_set_temp = cache_set[new_order]
        for i in current_order:
            cache_set[i] = cache_set_temp[i]

    def reserve_space_for_incoming_block(self, address, state):
        """
        find an available block slot for <address> in the corresponding cache_set, if the cache_set is full, i.e. all
        blocks are valid, then the least recently accessed block will be evicted. Once a slot is secured replace that
        slot with <address> block and write protect it by setting its lock bit to WRITE_LOCKED.
        :param address:
        :return:
        """
        tag, set_index, offset = self.resolve_memory_address(address)
        target_block = None
        for block in self.data[set_index]:
            if block[1] == INVALID:
                target_block = block

        if target_block is None:
            self.evict_block(self.data[set_index][-1])
            target_block = self.data[set_index][-1]

        target_block[0] = tag
        target_block[1] = state
        target_block[2] = WRITE_LOCKED

    def evict_block(self, block):
        pass

    def get_address_from_pieces(self, tag, cache_set_index, block_offset=0):
        address = block_offset
        tag = tag << self.m + self.n
        index = cache_set_index << self.n
        address = address | tag | index
        return address
