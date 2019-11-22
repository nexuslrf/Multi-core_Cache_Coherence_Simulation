import os

from components.dragoncache import DragonCache
from components.memorycontroller import MemoryController
from components.mesibus import Bus
from components.mesicache import MesiCache
from components.moesicache import MoesiCache
from opstream import OpStream
from components.processor import Processor
import util
from opts import args


def create_proc(i, protocol, limit, **kwargs):
    proc = Processor(i, limit=limit, **kwargs)
    if protocol == 'MESI':
        proc.cache = MesiCache(name='P' + str(i), **kwargs)
    elif protocol == 'MOESI':
        proc.cache = MoesiCache(name='P' + str(i), **kwargs)
    elif protocol == 'DRAGON':
        proc.cache = DragonCache(name='P' + str(i), **kwargs)
    return proc


def connect_bus(procs, bus):
    for proc in procs:
        proc.cache.bus = bus
        bus.connected_caches.append(proc.cache)
    return bus


def create_opstream(data_name, num_cores):
    dir_path = data_name
    result = []
    for i in range(num_cores):
        for file in os.listdir(dir_path):
            if str(i) in file:
                opstream = OpStream(dir_path+file)
                result.append(opstream)
    return result


class Simulator:
    def __init__(self, protocol='mesi', data='blackscholes_four', num_cores=4, memory_controller=MemoryController(),
                 limit=0, **kwargs):
        self.memory_controller = memory_controller
        # setup processors with caches
        self.procs = [create_proc(i, protocol, memory_controller=memory_controller, limit=limit, **kwargs) for i in range(num_cores)]
        # setup op stream for each processor
        if data:
            for proc, opstream in zip(self.procs, create_opstream(data, num_cores)):
                proc.op_stream = opstream
        # setup bus
        self.bus = connect_bus(self.procs, Bus())
        # cycle counter
        self.counter = 0
        util.counter = 0

    def run(self):
        while self.tick():
            for proc in self.procs:
                if proc.done_job_counter % 10000 == 0 and proc.done_job_counter // 10000 > 0:
                    print("{}: {} jobs done.".format(proc.cache.name, proc.done_job_counter))
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

        # tick the clock cycle once for every component, processors first, then caches, then memory
        for p in self.procs:
            p.tick()

        for p in self.procs:
            p.cache.tick()

        self.memory_controller.tick()

        self.counter += 1
        util.counter += 1
        return True


def collect_statistics(sim:Simulator):
    import pandas as pd
    out_dir = './output'
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    stats = {}
    stats['Overall Execution Cycle'] = sim.counter
    stats['Bus Data Traffic'] = sim.bus.total_bus_traffic
    stats['Bus Invalidation/Updates'] = sim.bus.total_bus_invalidation_or_updates
    stats['Private Data Access Percentage'] = 100*sum([x.cache.total_private_accesses for x in sim.procs])/sum([x.cache.total_access_count for x in sim.procs])
    stats_df = pd.DataFrame.from_dict({'stats':stats})
    stats_df = stats_df.astype(int)
    stats_df.to_csv('./output/overall.csv')
    print(stats_df)

    stats_per_core = {}
    for proc in sim.procs:
        stats_per_core[proc.cache.name] = {
            'Compute Cycles': int(proc.total_compute_cycles),
            'Load/Store Instructions': int(proc.total_store_instructions + proc.total_load_instructions),
            'Idle Cycles': int(proc.counter - proc.total_compute_cycles),
            'Cache Miss Rate': round(proc.cache.cache_miss_count / proc.cache.total_access_count, 2)
        }
    stats_per_core_df = pd.DataFrame.from_dict(stats_per_core)
    stats_per_core_df.to_csv('./output/percore.csv')
    print(stats_per_core_df)


if __name__ == '__main__':
    sim = Simulator(protocol=args.protocol, data=args.input_file,
                    block_size=args.block_size, assoc=args.associativity,
                    size=args.cache_size, limit=6000)
    sim.run()
    collect_statistics(sim)
