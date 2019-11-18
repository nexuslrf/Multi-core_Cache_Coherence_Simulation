from memorycontroller import MemoryController


class SimpleRequester:
    def __init__(self, name, mc):
        self.mc = mc
        self.name = name

    def on_fetch_from_memory_finished(self):
        print("[{}]{} fetch from memory finished".format(self.mc.counter, self.name))

    def on_evict_to_memory_finished(self):
        print("[{}]{} evict to memory finished".format(self.mc.counter, self.name))


def test_memory_controller():
    mc = MemoryController()
    r0 = SimpleRequester('P0', mc)
    r1 = SimpleRequester('P1', mc)
    r2 = SimpleRequester('P2', mc)
    r3 = SimpleRequester('P3', mc)
    mc.fetch_block(r0, 0b1)
    for _ in range(99):
        mc.tick()

    mc.evict_block(r1, 0b10)
    for _ in range(40):
        mc.tick()

    mc.evict_block(r2, 0b10)
    for _ in range(100):
        mc.tick()

    mc.fetch_block(r0, 0b11)
    for _ in range(100):
        mc.tick()
