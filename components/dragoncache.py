from components.cachebase import CacheBase
from constants.cache import *
from constants.jobtype import *
from constants.locking import *
from constants.mesi import *
from job import CacheJob
from util import resolve_memory_address


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
            pass

    def send_job_specific_bus_request(self):
        pass

    def handle_proc_read(self, job):
        block = self.get_cache_block(job.address)
        if block is not None:
            if block[1] != INVALID:
                self.start_hitting()
        else:
            # @TODO check it!
            self.bus.apply_for_bus_master(self, self.bus_control_granted)

    # @TODO check it!
    # def bus_control_granted(self, result):
    #     if result:  # bus ownership granted
    #         self.allocate_block(self.current_job.address)
    #         self.send_job_specific_bus_request()
    #     else:  # bus ownership rejected
    #         return  # start over next time
    #
    # def allocate_block(self, address):
    #     # check if block exists in cache
    #     tag, set_index, offset = self.resolve_memory_address(address)
    #     for block in self.data[set_index]:
    #         if block[0] == tag:
    #             return
