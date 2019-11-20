from components.memorycontroller import MemoryController


class SimpleRequester:
    def __init__(self, name, mc):
        self.mc = mc
        self.name = name
        self.fetched_block = None
        self.evicted_block = None

    def on_fetch_from_memory_finished(self):
        self.fetched_block = 1

    def on_evict_to_memory_finished(self):
        self.evicted_block = 1

    def reset(self):
        self.fetched_block = None
        self.evicted_block = None


def test_fetch_block_from_memory():
    mc = MemoryController()
    r0 = SimpleRequester('P0', mc)
    r1 = SimpleRequester('P1', mc)
    r2 = SimpleRequester('P2', mc)
    mc.fetch_block(r0, 0b1)
    for _ in range(99):
        mc.tick()
    assert r0.fetched_block is None
    mc.tick()
    assert r0.fetched_block is not None
    r0.reset()

    mc.fetch_block(r0, 0b1)
    for _ in range(50):
        mc.tick()
    assert r0.fetched_block is None
    mc.fetch_block(r1, 0b1)
    mc.fetch_block(r2, 0b11)
    for _ in range(50):
        mc.tick()
    assert r0.fetched_block is not None
    assert r1.fetched_block is None
    assert r2.fetched_block is None
    for _ in range(50):
        mc.tick()
    assert r1.fetched_block is not None
    assert r2.fetched_block is not None


def test_evict_block_to_memory():
    mc = MemoryController()
    r0 = SimpleRequester('P0', mc)
    r1 = SimpleRequester('P1', mc)
    r2 = SimpleRequester('P2', mc)
    mc.evict_block(r0, 0b1)
    for _ in range(99):
        mc.tick()
    assert r0.evicted_block is None
    mc.tick()
    assert r0.evicted_block is not None
    r0.reset()

    mc.evict_block(r0, 0b1)
    for _ in range(50):
        mc.tick()
    assert r0.evicted_block is None
    mc.evict_block(r1, 0b1)
    mc.evict_block(r2, 0b11)
    for _ in range(50):
        mc.tick()
    assert r0.evicted_block is not None
    assert r1.evicted_block is None
    assert r2.evicted_block is None
    for _ in range(50):
        mc.tick()
    assert r1.evicted_block is not None
    assert r2.evicted_block is not None


def test_interleaving_evict_and_fetch_memory():
    mc = MemoryController()
    r0 = SimpleRequester('P0', mc)
    r1 = SimpleRequester('P1', mc)
    r2 = SimpleRequester('P2', mc)
    mc.fetch_block(r0, 0b1)
    for _ in range(50):
        mc.tick()
    assert r0.fetched_block is None
    mc.evict_block(r0, 0b10)
    mc.evict_block(r1, 0b1)
    mc.evict_block(r2, 0b11)
    for _ in range(50):
        mc.tick()
    assert r0.fetched_block is not None
    assert r0.evicted_block is None
    assert r1.evicted_block is None
    assert r2.evicted_block is None
    for _ in range(50):
        mc.tick()
    assert r0.evicted_block is not None
    assert r1.evicted_block is not None
    assert r2.evicted_block is not None
