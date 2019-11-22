from math import log

import numpy as np

from components.cachebase import CacheBase
from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.moesi import *
from job import CacheJob
from util import resolve_memory_address, debug


class MoesiCache(CacheBase):
    def __init__(self, name, size=4096, assoc=2, block_size=32, memory_controller=None, bus=None):
        super().__init__(name, size, assoc, block_size, memory_controller, bus)

    def interim(self):
        # run interim stuff if there is a current job
        if self.current_job is None:
            return

        if self.current_job.status_in_cache == FRESH:
            self.handle_fresh_job(self.current_job)

        if self.current_job.status_in_cache == BUS_OWNERSHIP_PENDING:
            self.bus.apply_for_bus_master(self, self.bus_control_granted)

        if self.current_job.status_in_cache == OTHER_SIDE_BLOCKING:
            self.send_job_specific_bus_request()

    def handle_fresh_job(self, job):
        local_hit = False
        if job.type == LOAD:
            local_hit = self.handle_proc_read(job)
        if job.type == STORE:
            local_hit = self.handle_proc_write(job)
        if not local_hit:
            self.current_job.status_in_cache = BUS_OWNERSHIP_PENDING
            self.bus.apply_for_bus_master(self, self.bus_control_granted)

    def handle_proc_read(self, job):
        block = self.get_cache_block(job.address)
        if block is not None:
            self.start_hitting()
            return True
        return False

    def handle_proc_write(self, job):
        block = self.get_cache_block(job.address)
        if block is not None:
            if block[1] in [MODIFIED, EXCLUSIVE]:
                self.start_hitting()
                return True
        return False

    def bus_control_granted(self, result):
        if result:  # bus ownership granted
            self.send_job_specific_bus_request()
        else:  # bus ownership rejected
            return  # start over next time

    def get_cache_block(self, address):
        """
        get the cache block that contains the address, note that blocks in Invalid state will not be returned, even
        though their tag and index has a match.
        :param address: 32-bit memory address
        :return: None if block containing this address is not found in cache, otherwise the found block
        """
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag and block[1] != INVALID:
                return block

        return None

    def send_job_specific_bus_request(self):
        if self.current_job.type == LOAD:
            result, self.payload_words, mem_wait_passive = self.bus.send_read_req(self, self.current_job.address)
        else:
            result, self.payload_words, mem_wait_passive = self.bus.send_read_X_req(self, self.current_job.address)

        if not result:
            self.current_job.status_in_cache = OTHER_SIDE_BLOCKING
            return

        mem_wait = self.reserve_space_for_incoming_block(self.current_job.address)

        if mem_wait or mem_wait_passive:
            self.current_job.status_in_cache = WAITING_FOR_MEMORY
            return

        self.proceed_with_bus_payload(self.payload_words)

    def proceed_with_bus_payload(self, payload_words):
        if self.current_job.type == LOAD:
            if payload_words:
                self.set_block_state(self.current_job.address, SHARED)
                self.current_job.status_in_cache = RECEIVING_FROM_BUS
                self.current_job.remaining_bus_read_cycles = payload_words * 2
                debug("{} start reading from Bus: {} cycles".format(self.name,
                                                                    self.current_job.remaining_bus_read_cycles))
            else:
                self.set_block_state(self.current_job.address, EXCLUSIVE)
                self.cache_miss_count += 1
                self.bus.release_ownership(self)
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY
                debug("{} start fetching from Mem: 100 cycles".format(self.name))

        if self.current_job.type == STORE:
            if self.get_cache_block(self.current_job.address) is not None:  # block is present, invalidation only
                self.set_block_state(self.current_job.address, MODIFIED)
                self.on_bus_read_finished()
            elif payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.set_block_state(self.current_job.address, MODIFIED)
                self.current_job.status_in_cache = RECEIVING_FROM_BUS
                self.current_job.remaining_bus_read_cycles = payload_words * 2
            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.bus.release_ownership(self)
                self.set_block_state(self.current_job.address, MODIFIED)
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY

    def unlock_block(self, address):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[2] = UNLOCKED

    def start_hitting(self):
        tag, set_index, _ = self.resolve_memory_address(self.current_job.address)
        self.update_cache_set_access_order(set_index, tag)
        if self.current_job.type == LOAD:
            self.lock_block(self.current_job.address, READ_LOCKED)
        if self.current_job.type == STORE:
            self.lock_block(self.current_job.address, WRITE_LOCKED)
        self.current_job.status_in_cache = HITTING

        # statistics record
        if self.get_cache_block(self.current_job.address)[1] != SHARED:
            self.total_private_accesses += 1

    def on_hit_finished(self):
        if self.current_job.type == STORE:
            self.set_block_state(self.current_job.address, MODIFIED)
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

    def on_bus_read_finished(self):
        self.bus.release_ownership(self)  # throws exception if self is not current bus owner!
        self.start_hitting()

    def on_fetch_from_memory_finished(self):
        self.start_hitting()

    def on_evict_to_memory_finished(self):

        self.proceed_with_bus_payload(self.payload_words)

    def bus_read(self, address):
        """

        :param address:
        :return: tuple(Boolean, Int) Boolean value is False if the block is available but being locked, otherwise True
        Int value is the payload size if the block is available and ready to be transmitted, or 0 if block not found.
        """
        block = self.get_cache_block(address)
        mem_op = False
        if block is not None:
            if block[2] > READ_LOCKED:
                return False, 0, mem_op
            if block[1] in [SHARED, OWNED]:
                return True, self.block_size//4, mem_op
            if block[1] == EXCLUSIVE:
                block[1] = SHARED
                return True, self.block_size//4, mem_op
            if block[1] == MODIFIED:
                block[1] = OWNED
                return True, self.block_size//4, mem_op

        return True, 0, mem_op

    def bus_readx(self, address):
        block = self.get_cache_block(address)
        mem_op = False
        if block is not None:
            if block[2] > UNLOCKED:
                return False, 0, mem_op
            if block[1] == SHARED:
                block[1] = INVALID
                return True, self.block_size // 4, mem_op
            if block[1] == EXCLUSIVE:
                block[1] = INVALID
                return True, self.block_size // 4, mem_op
            if block[1] in [MODIFIED, OWNED]:
                block[1] = INVALID
                mem_op = True
                return True, self.block_size // 4, mem_op

        return True, 0, mem_op
