import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--protocol', default='MESI', type=str)
parser.add_argument('--input_file', default='blackscholes', type=str)
parser.add_argument('--cache_size', default=4096, type=int)
parser.add_argument('--associativity', default=2, type=int)
parser.add_argument('--block_size', default=32, type=int)
parser.add_argument('--bus_mem_op', action='store_true')

args = parser.parse_args()