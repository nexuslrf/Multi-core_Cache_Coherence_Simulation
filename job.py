from constants.cache import *


class Job:
    def __init__(self, job_type, address=None, remaining_cycles=None):
        self.address = address
        self.type = 0
        self.countdown_cycles = remaining_cycles

    @staticmethod
    def create_from_op(op):
        opcode, value = op

        if opcode == 2:
            cpu_job = Job(job_type=opcode, remaining_cycles=value)
            return cpu_job
        if opcode == 0 or opcode == 1:
            mem_job = Job(job_type=opcode, address=value)
            return mem_job


class CacheJob(Job):
    def __init__(self, job_type, **kwargs):
        self.status_in_cache = FRESH
        super().__init__(job_type, **kwargs)

    @staticmethod
    def create_from_job(job, offset_bits):
        """
        create cache job from processor Load/Store job, where the memory address will be masked to block index
        :param job: CPU job
        :param offset_bits: number of bits of the block offset in the corresponding Cache
        :return: a cache job
        """
        block_address = job.address >> offset_bits << offset_bits
        cache_job = CacheJob(job.type, address=block_address, remaining_cycles=job.countdown_cycles)
        return cache_job
