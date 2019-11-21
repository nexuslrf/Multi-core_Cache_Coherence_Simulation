from job import Job
from util import debug


class Processor:
    def __init__(self, i, **kwargs):
        self.index = i
        self.current_job = None
        self.op_stream = None
        self.cache = None
        self.done = False
        self.done_job_counter = -1
        self.counter = 0

    def interim(self):
        """
        Execute all interim operations that takes place before the next clock cycle
        :return: None
        """
        if self.is_busy() or self.cache.is_busy() or self.done:
            return
        else:
            self.done_job_counter += 1
            job = self.fetch_next_job()
            if not job:
                self.done = True
                return
            if job.type > 1:  # CPU job
                debug("{} schedule CPU job: {} cycles".format(self.cache.name, job.countdown_cycles))
                self.schedule_job(job)
            else:  # mem job
                debug("{} schedule Cache job: {}".format(self.cache.name, 'STORE' if job.type else 'LOAD'))
                self.cache.schedule_job(job)

    def fetch_next_job(self):
        """
        fetch next job from the job stream
        :return: the next job, None if reaching the end of stream
        """
        op = self.op_stream.read_op()
        if op:
            job = Job.create_from_op(op)
            return job
        else:
            return None

    def schedule_job(self, job):
        self.current_job = job

    def is_busy(self):
        return self.current_job is not None

    def tick(self):
        if self.done:
            return
        if self.is_busy():
            self.current_job.countdown_cycles -= 1
            if self.current_job.countdown_cycles < 1:
                self.current_job = None
        self.counter += 1
