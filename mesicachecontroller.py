from collections import deque
from math import log

import numpy as np

from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.mesi import *
from job import CacheJob
from util import resolve_memory_address


class MesiCacheController:
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
        self.access_history = {}  # {set_index: deque[]}
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
        if self.current_job is None:
            return

        if self.current_job.status_in_cache == FRESH:
            self.handle_fresh_job(self.current_job)

        if self.current_job.status_in_cache == OTHER_SIDE_BLOCKING:
            self.send_job_specific_bus_request()

    def handle_fresh_job(self, job):
        if job.type == LOAD:
            self.handle_proc_read(job)
        if job.type == STORE:
            pass

    def handle_proc_read(self, job):
        block = self.get_cache_block(job.address)
        if block is not None:
            if block[1] != INVALID:
                self.start_hitting()
                return
        self.bus.apply_for_bus_master(self, self.bus_control_granted)

    def handle_proc_write(self, job):
        block = self.get_cache_block(job.address)
        if block is not None:
            if block[1] in [MODIFIED, EXCLUSIVE]:
                self.start_hitting()
                return
            # TODO do we still need to handle Shared and Invalid cases
        self.bus.apply_for_bus_master(self, self.bus_control_granted)

    def bus_control_granted(self, result):
        if result:  # bus ownership granted
            self.allocate_block(self.current_job.address)
            self.send_job_specific_bus_request()
        else:  # bus ownership rejected
            return  # start over next time

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

    def send_job_specific_bus_request(self):
        if self.current_job.type == LOAD:
            result, payload_words = self.bus.send_read_req(self, self.current_job.address)
            if not result:
                self.current_job.status_in_cache = OTHER_SIDE_BLOCKING
            elif payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.set_block_state(self.current_job.address, EXCLUSIVE)
                self.current_job.status_in_cache = RECEIVING_FROM_BUS
                self.current_job.remaining_bus_read_cycles = payload_words * 2
            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.set_block_state(self.current_job.address, EXCLUSIVE)
                self.lock_block(self.current_job.address)
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY

        if self.current_job.type == STORE:
            self.set_block_state(self.current_job.address, MODIFIED)
            self.lock_block(self.current_job.address)
            result, payload_words = self.bus.send_read_X_req(self, self.current_job.address)
            if not result:
                self.current_job.status_in_cache = OTHER_SIDE_BLOCKING
            elif payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.current_job.status_in_cache = RECEIVING_FROM_BUS
                self.current_job.remaining_bus_read_cycles = payload_words * 2
            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.lock_block(self.current_job.address)
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY

    def on_bus_read_finished(self):
        self.bus.release_ownership(self)  # throws exception if self is not current bus owner!
        self.start_hitting()

    def unlock_block(self, address):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[2] = UNLOCKED

    def start_hitting(self):
        self.current_job.status_in_cache = HITTING

    def on_hit_finished(self):
        self.unlock_block(self.current_job.address)
        self.current_job = None

    def set_block_state(self, address, state):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[1] = state
                return

        raise LookupError("[set_block_state] block not found in cache")

    def lock_block(self, address, lock=READ_LOCKED):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[2] = lock
                return

        raise LookupError("[lock_block] block not found in cache")

    def on_fetch_from_memory_finished(self):
        self.start_hitting()

    def allocate_block(self, address):
        # check if block exists in cache
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                return

        # if not exist choose first empty/invalid block
        # write tag of address to that block
        for block in self.data[set_index]:
            if block[1] == INVALID:
                old_tag = block[0]
                block[0] = tag
                return

        # otherwise, have to evict existing block
        old_tag = self.access_history[set_index].popleft()
        self.access_history[set_index].append(tag)
        evict_address = old_tag<<(self.m+self.n) + set_index << self.n + offset
        self.memory_controller.evict_block(self, evict_address)

    def resolve_memory_address(self, address):
        return resolve_memory_address(address, self.set_index_mask, self.offset_mask, self.m, self.n)

    def update_access_history(self, address):
        tag, set_index, offset = self.resolve_memory_address(address)
        set_history = self.access_history.setdefault(set_index, deque(self.assoc*[0], self.assoc))
        if tag in set_history:
            set_history.remove(tag)
        set_history.append(tag)

    def bus_read(self, address):
        block = self.get_cache_block(address)
        if block is not None:
            if block[1] == SHARED:
                return True, self.block_size//4
