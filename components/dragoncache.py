from components.cachebase import CacheBase
from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.dragon import *
# from constants.mesi import *
from job import CacheJob
from util import resolve_memory_address

from util import resolve_memory_address, debug

# tt = 0

class DragonCache(CacheBase):
    def __init__(self, name, size=4096, assoc=2, block_size=32, memory_controller=None, bus=None, bus_mem_op=False):
        super().__init__(name, size, assoc, block_size, memory_controller, bus)
        self.bus_mem_op = bus_mem_op

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
            if block[1] != INVALID:
                self.start_hitting()
                return True
        return False

    def handle_proc_write(self, job):
        block = self.get_cache_block(job.address)
        if block is not None:
            if block[1] in [EC, M]:
                self.start_hitting()
                return True
        return False

    def bus_control_granted(self, result):
        if result:  # bus ownership granted
            self.send_job_specific_bus_request()
        else:  # bus ownership rejected
            return  # start over next time

    def send_job_specific_bus_request(self):
        # global tt
        mem_wait_passive = False
        if self.current_job.type == LOAD:
            result, self.payload_words, mem_wait_passive = self.bus.send_read_req(self, self.current_job.address)
        else:
            result, self.payload_words = self.bus.send_update_req(self, self.current_job.address)

        if not result:
            self.current_job.status_in_cache = OTHER_SIDE_BLOCKING
            return
        # if tt==416: print()
        mem_wait = self.reserve_space_for_incoming_block(self.current_job.address)
        # tt += 1
        if mem_wait or mem_wait_passive:
            self.current_job.status_in_cache = WAITING_FOR_MEMORY
            return

        self.proceed_with_bus_payload(self.payload_words)

    def proceed_with_bus_payload(self, payload_words):
        if self.current_job.type == LOAD:
            if payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.set_block_state(self.current_job.address, SC)
                self.current_job.status_in_cache = RECEIVING_FROM_BUS
                self.current_job.remaining_bus_read_cycles = payload_words * 2
                debug("{} start reading from Bus: {} cycles".format(self.name, self.current_job.remaining_bus_read_cycles))

            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.set_block_state(self.current_job.address, EC)
                self.cache_miss_count += 1
                self.bus.release_ownership(self)
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY
                debug("{} start fetching from Mem: 100 cycles".format(self.name))

        if self.current_job.type == STORE:

            if payload_words:  # result comes with payload, data will be supplied by one of other caches
                self.bus.send_lock_req(self, self.current_job.address, WRITE_LOCKED)
                self.set_block_state(self.current_job.address, SM)
                self.current_job.status_in_cache = WAITING_FOR_BUS_UPD
                # @TODO cycles for whom?
                self.current_job.remaining_bus_read_cycles = 2
            else:  # result comes without payload, other caches do not have copy, therefore fetch from memory
                self.bus.release_ownership(self)
                self.set_block_state(self.current_job.address, M)
                # @TODO ignore mem ops.
                self.memory_controller.fetch_block(self, self.current_job.address)
                self.current_job.status_in_cache = WAITING_FOR_MEMORY

    def start_hitting(self):
        tag, set_index, _ = self.resolve_memory_address(self.current_job.address)
        self.update_cache_set_access_order(set_index, tag)
        if self.current_job.type == LOAD:
            self.lock_block(self.current_job.address, READ_LOCKED)
        if self.current_job.type == STORE:
            self.lock_block(self.current_job.address, WRITE_LOCKED)
        self.current_job.status_in_cache = HITTING

        # statistics record
        if self.get_cache_block(self.current_job.address)[1] not in [SC, SM]:
            self.total_private_accesses += 1

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
        if self.current_job.status_in_cache == WAITING_FOR_BUS_UPD:
            self.bus.send_lock_req(self, self.current_job.address, UNLOCKED)
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
            if block[1] == SC:
                return True, self.block_size//4, mem_op
            elif block[1] == EC:
                block[1] = SC
                return True, self.block_size//4, mem_op
            elif block[1] == M:
                # self.evict_block_passive(block)
                if self.bus_mem_op:
                    mem_op = True
                block[1] = SM
                return True, self.block_size//4, mem_op
            elif block[1] == SM:
                # self.evict_block_passive(block)
                if self.bus_mem_op:
                    mem_op = True
                return True, self.block_size // 4, mem_op

        return True, 0, mem_op

    def bus_update(self, address):
        block = self.get_cache_block(address)
        if block is not None:
            if block[2] > UNLOCKED:
                return False, 0
            else:
                block[1] = SC
                return True, self.block_size // 4

        return True, 0

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

    def reserve_space_for_incoming_block(self, address):
        """
        find an available block slot for <address> in the corresponding cache_set, if the cache_set is full, i.e. all
        blocks are valid, then the least recently accessed block will be evicted. Once a slot is secured replace that
        slot with <address> block and write protect it by setting its lock bit to WRITE_LOCKED.
        :param address:
        :return: True if resulting in block eviction, otherwise False
        """
        tag, set_index, offset = self.resolve_memory_address(address)
        target_block = None
        need_eviction = False
        for block in self.data[set_index]:
            if block[0] == tag:
                target_block = block
                break
            if block[1] == INVALID:
                target_block = block
                break

        if target_block is None:
            target_block = self.data[set_index][-1]  # set to the least recently accessed block
            if target_block[1] == M:
                need_eviction = True
                self.evict_block(self.data[set_index][-1])
            elif target_block[1] == SM:
                blocks = self.bus.check_share_line(self, self.get_address_from_pieces(target_block[0], set_index))
                if len(blocks) == 1:
                    blocks[0][1] = EC
                elif len(blocks) > 1:
                    for b in blocks:
                        b[1] = SC
                need_eviction = True
                self.evict_block(self.data[set_index][-1])
            elif target_block[1] == SC:
                blocks = self.bus.check_share_line(self, self.get_address_from_pieces(target_block[0], set_index))
                if len(blocks) == 1:
                    blocks[0][1] = EC
                elif len(blocks) > 1:
                    for b in blocks:
                        b[1] = SC
            target_block[1] = INVALID

        target_block[0] = tag
        target_block[2] = WRITE_LOCKED
        return need_eviction
