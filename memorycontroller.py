class MemoryController:
    def __init__(self):
        self.counter = 0
        self.loading = {}
        self.loading_listeners = {}
        self.storing = {}
        self.storing_listerners = {}

    def fetch_block(self, requester, address):
        listeners = self.loading_listeners.setdefault(address, [])
        if listeners:
            raise PermissionError("cache {} is already fetching this address from memory".format(listeners[0].name))
        listeners.append(requester)
        self.loading[address] = 100

    def evict_block(self, requester, address):
        self.storing[address] = 100
        storing_listeners = self.storing_listerners.setdefault(address, [])
        storing_listeners.append(requester)

    def tick(self):
        self.counter += 1
        finished = []
        for address in self.loading:
            self.loading[address] -= 1
            if self.loading[address] == 0:
                finished.append(address)

        for address in finished:
            self.loading.pop(address)
            for listener in self.loading_listeners[address]:
                listener.on_fetch_from_memory_finished()
            self.loading_listeners.pop(address)

        finished = []
        for address in self.storing:
            self.storing[address] -= 1
            if self.storing[address] == 0:
                finished.append(address)

        for address in finished:
            self.storing.pop(address)
            for listener in self.storing_listerners[address]:
                listener.on_evict_to_memory_finished()
            self.storing_listerners.pop(address)
