from components.cachebase import CacheBase
from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.dragon import *
from constants.mesi import *
from job import CacheJob
from util import resolve_memory_address

from util import resolve_memory_address, debug


class DragonCache(CacheBase):
    def __init__(self, name, size=4096, assoc=2, block_size=32, memory_controller=None, bus=None):
        super().__init__(name, size, assoc, block_size, memory_controller, bus)

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
            self.handle_proc_write(job)

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
            if block[1] in [EC, M]:
                self.start_hitting()
                return
        self.bus.apply_for_bus_master(self, self.bus_control_granted)

    def bus_control_granted(self, result):
        if result:  # bus ownership granted
            self.send_job_specific_bus_request()
        else:  # bus ownership rejected
            return  # start over next time

    def send_job_specific_bus_request(self):
        if self.current_job.type == LOAD:
            result, payload_words = self.bus.send_read_req(self, self.current_job.address)
            if not result:
                self.current_job.status_in_cache = OTHER_SIDE_BLOCKING
            elif payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.reserve_space_for_incoming_block(self.current_job.address, SC)
                self.current_job.status_in_cache = RECEIVING_FROM_BUS
                self.current_job.remaining_bus_read_cycles = payload_words * 2
                debug("{} start reading from Bus: {} cycles".format(self.name, self.current_job.remaining_bus_read_cycles))
            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.bus.release_ownership(self)
                self.reserve_space_for_incoming_block(self.current_job.address, EC)
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY
                debug("{} start fetching from Mem: 100 cycles".format(self.name))

        if self.current_job.type == STORE:
            result, payload_words = self.bus.send_update_req(self, self.current_job.address)
            if not result:
                self.current_job.status_in_cache = OTHER_SIDE_BLOCKING
            elif payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.bus.send_lock_req(self, self.current_job.address, WRITE_LOCKED)
                self.reserve_space_for_incoming_block(self.current_job.address, SM)
                self.current_job.status_in_cache = WAITING_FOR_BUS_UPD
                # @TODO cycles for whom?
                self.current_job.remaining_bus_read_cycles = payload_words * 2
            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.bus.release_ownership(self)
                self.reserve_space_for_incoming_block(self.current_job.address, M)
                # @TODO ignore mem ops.
                # self.memory_controller.fetch_block(self, self.current_job.address)
                # self.current_job.status_in_cache = WAITING_FOR_MEMORY

    def start_hitting(self):
        tag, set_index, _ = self.resolve_memory_address(self.current_job.address)
        self.update_cache_set_access_order(set_index, tag)
        if self.current_job.type == LOAD:
            self.lock_block(self.current_job.address, READ_LOCKED)
        if self.current_job.type == STORE:
            self.lock_block(self.current_job.address, WRITE_LOCKED)
        self.current_job.status_in_cache = HITTING

    def on_hit_finished(self):
        if self.current_job.type == STORE:
            block = self.get_cache_block(self.current_job.address)
            if block[1] == EC:
                block[1] = M
            elif block[1] == SC:
                block[1] = SM
        self.unlock_block(self.current_job.address)
        self.current_job = None

    def set_block_state(self, address, state):
        tag, set_index, offset = self.resolve_memory_address(address)
        for block in self.data[set_index]:
            if block[0] == tag:
                block[1] = state
                return

        raise LookupError("[set_block_state] block not found in cache")

    def on_bus_read_finished(self):
        self.bus.release_ownership(self)  # throws exception if self is not current bus owner!
        if self.current_job.status_in_cache == WAITING_FOR_BUS_UPD:
            self.bus.send_lock_req(self, self.current_job.address, UNLOCKED)
        self.start_hitting()

    def on_fetch_from_memory_finished(self):
        self.start_hitting()

    def bus_read(self, address):
        """

        :param address:
        :return: tuple(Boolean, Int) Boolean value is False if the block is available but being locked, otherwise True
        Int value is the payload size if the block is available and ready to be transmitted, or 0 if block not found.
        """
        block = self.get_cache_block(address)
        if block is not None:
            if block[2] > READ_LOCKED:
                return False, 0
            if block[1] in [SC, SM]:
                return True, self.block_size//4
            if block[1] == EC:
                block[1] = SC
                return True, self.block_size//4
            if block[1] == M:
                block[1] = SM
                return True, self.block_size//4

        return True, 0

    def bus_update(self, address):
        block = self.get_cache_block(address)
        if block is not None:
            if block[2] > UNLOCKED:
                return False, 0
            if block[1] in [SM, SC]:
                block[1] = SC
                return True, self.block_size // 4

        return True, 0

    def evict_block(self, block):
