class MemoryController:
    def __init__(self):
        self.loading = {}
        self.storing = {}

    def fetch_block(self, requester, address):
        self.loading[requester] = 100

    def evict_block(self, requester, address):
        self.storing[requester] = 100

    def tick(self):
        for requester in self.loading:
            self.loading[requester] -= 1
            if self.loading[requester] < 1:
                requester.on_fetch_from_memory_finished()

        for requester in self.storing:
            self.storing[requester] -= 1
            if self.storing[requester] < 1:
                requester.on_evict_to_memory_finished()
