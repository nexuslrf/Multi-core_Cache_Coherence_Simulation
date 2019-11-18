from mesibus import Bus
from mesicachecontroller import MesiCacheController
from processor import Processor


def create_proc(i, protocol, **kwargs):
    proc = Processor(i, **kwargs)
    if protocol == 'mesi':
        proc.cache = MesiCacheController(name='P' + i, **kwargs)
    # if protocol == 'dragon':
    #     proc.cache = DragonCacheController(name='P' + i, **kwargs)
    return proc


def connect_bus(procs, bus):
    for proc in procs:
        proc.cache.bus = bus
        bus.connected_caches.append(proc.cache)
    return bus


class Simulator:
    def __init__(self, protocol='mesi', *args, **kwargs):
        self.procs = [create_proc(i, protocol, **kwargs) for i in range(4)]
        # setup bus
        self.bus = connect_bus(self.procs, Bus())

    def run(self):
        while self.tick():
            continue

        print("All Finished!")

    def tick(self):
        """

        :return: True if all processors have finished running.
        """
        # check if all cores finished running
        done_count = 0
        for processor in self.procs:
            if processor.done:
                done_count += 1
        if done_count == len(self.procs):
            # exit the program
            print('Game Over')
            return False

        # run every component's interim operations, processors first, then caches, then bus
        for p in self.procs:
            p.interim()

        for p in self.procs:
            p.cache.interim()

        self.bus.interim()

        # tick the clock cycle once for every component, processors first, then caches (bus does not have this)
        for p in self.procs:
            p.tick()

        for p in self.procs:
            p.cache.tick()

        return True
