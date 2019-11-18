from job import Job
from mesicachecontroller import MesiCacheController


class Processor:
    def __init__(self, i, **kwargs):
        self.index = i
        self.current_job = None
        self.op_stream = None
        self.cache = None
        self.done = False

    def interim(self):
        """
        Execute all interim operations that takes place before the next clock cycle
        :return: None
        """
        if self.is_busy() or self.cache.is_busy():
            return
        else:
            job = self.fetch_next_job()
            if not job:
                self.done = True
                return
            if job.category > 1:  # CPU job
                self.schedule_job(job)
            else:  # mem job
                self.cache.schedule_job(job)

    def fetch_next_job(self):
        """
        fetch next job from the job stream
        :return: the next job, None if reaching the end of stream
        """
        op = self.op_stream.read_op()
        job = Job.create_from_op(op)
        return job

    def schedule_job(self, job):
        self.current_job = job

    def is_busy(self):
        return self.current_job is not None

    def tick(self):
        self.current_job.countdown_cycles -= 1
        if self.current_job.countdown_cycles < 1:
            self.current_job = None