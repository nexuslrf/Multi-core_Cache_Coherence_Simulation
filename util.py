import os


def resolve_memory_address(address, set_index_mask, block_offset_mask, m, n):
    tag = address & ~(set_index_mask | block_offset_mask)
    tag = tag >> m+n
    set_index = address & set_index_mask
    set_index = set_index >> n
    offset = address & block_offset_mask
    return tag, set_index, offset


counter = 0
visited_counter = -1


def debug(content):
    global visited_counter
    if "ASS2_DEBUGGING" in os.environ:
        if visited_counter < counter:
            print("-------------clock {}-------------".format(counter + 1))
            visited_counter = counter
        print(content)
