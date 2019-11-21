import numpy as np

from main import Simulator
from opstream import FakeOpStream
from constants.dragon import *


def test_cache_direct_hit_only():
    op_list = [(0, 0b100000100001), (0, 0b1000000110000), (0, 0b100000100111), (0, 0b1000000110011)]
    simulator = Simulator(protocol='dragon', data=None, num_cores=1)
    simulator.procs[0].op_stream = FakeOpStream(op_list)
    simulator.procs[0].cache.data[1] = np.matrix([
        [1, SC, 0],
        [2, SC, 0]
    ])
    simulator.run()
    assert simulator.counter == len(op_list)
