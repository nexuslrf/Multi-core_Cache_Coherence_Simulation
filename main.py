import os

from components.mesibus import Bus
from components.mesicachecontroller import MesiCacheController
from opstream import OpStream
from components.processor import Processor


def create_proc(i, protocol, **kwargs):
    proc = Processor(i, **kwargs)
    if protocol == 'mesi':
        proc.cache = MesiCacheController(name='P' + str(i), **kwargs)
    # if protocol == 'dragon':
    #     proc.cache = DragonCacheController(name='P' + i, **kwargs)
    return proc


def connect_bus(procs, bus):
    for proc in procs:
        proc.cache.bus = bus
        bus.connected_caches.append(proc.cache)
    return bus


def create_opstream(data_name, num_cores):
    dir_path = './data/{}/'.format(data_name)
    result = []
    for i in range(num_cores):
        for file in os.listdir(dir_path):
            if str(i) in file:
                opstream = OpStream(dir_path+file)
                result.append(opstream)
    return result


class Simulator:
    def __init__(self, protocol='mesi', data='blackscholes_four', num_cores=4, *args, **kwargs):
        # setup processors with caches
        self.procs = [create_proc(i, protocol, **kwargs) for i in range(num_cores)]
        # setup op stream for each processor
        if data:
            for proc, opstream in zip(self.procs, create_opstream(data, num_cores)):
                proc.op_stream = opstream
        # setup bus
        self.bus = connect_bus(self.procs, Bus())
        # cycle counter
        self.counter = 0

    def run(self):
        while self.tick():
            continue

        print("All Finished! Current counter: {}".format(self.counter))
        for proc in self.procs:
            print('processsor {0} counter: {1}'.format(proc.index, proc.counter))

    def tick(self):
        """
        :return: True if all processors have finished running.
        """
        # run every component's interim operations, processors first, then caches, then bus
        for p in self.procs:
            p.interim()

        for p in self.procs:
            p.cache.interim()

        self.bus.interim()

        # check if all cores finished running
        done_count = 0
        for processor in self.procs:
            if processor.done:
                done_count += 1
        if done_count == len(self.procs):
            # exit the program
            print('Game Over')
            return False

        # tick the clock cycle once for every component, processors first, then caches (bus does not have this)
        for p in self.procs:
            p.tick()

        for p in self.procs:
            p.cache.tick()

        self.counter += 1
        return True
