import random

from util import debug

# xx_cnt = 0

class Bus:
    def __init__(self):
        self.connected_caches = []
        self.applicants = []
        self.bus_master = None
        self.total_bus_invalidation_or_updates = 0
        self.total_bus_traffic = 0  # unit in bytes

    def apply_for_bus_master(self, cache, callback):
        self.applicants.append((cache, callback))

    def release_ownership(self, caller):
        # global xx_cnt
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                      self.bus_master.name))
        # xx_cnt += 1
        # if xx_cnt >= 417: print()
        self.bus_master = None

    def interim(self):
        if self.applicants:
            self.process_applications()

    def process_applications(self):
        if self.bus_master is not None:
            for _, callback in self.applicants:
                callback(False)

        else:
            selected_index = 0  # always select the first applicant in the list, i.e. processor 0
            # selected_index = random.randint(1, len(self.applicants)) - 1
            for i in range(len(self.applicants)):
                if i == selected_index:
                    selected_applicant, callback = self.applicants[i]
                    self.bus_master = selected_applicant
                    debug("Bus granted to {}".format(selected_applicant.name))
                    callback(True)
                else:
                    _, callback = self.applicants[i]
                    callback(False)
        self.applicants.clear()

    def send_read_req(self, caller, address):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        aggregated_payload = 0
        aggregated_response = True
        wait_mem = False
        for cache in self.connected_caches:
            if cache != caller:
                response, payload_words, mem_op = cache.bus_read(address)
                aggregated_response = aggregated_response and response
                wait_mem = wait_mem or mem_op
                if payload_words:
                    aggregated_payload = payload_words
        if wait_mem:
            caller.evict_block_passive(address)
        if aggregated_response and aggregated_payload:
                self.total_bus_traffic += aggregated_payload * 4
        return aggregated_response, aggregated_payload, wait_mem

    def send_read_X_req(self, caller, address):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        aggregated_payload = 0
        aggregated_response = True
        wait_mem = False
        for cache in self.connected_caches:
            if cache != caller:
                response, payload_words, mem_op = cache.bus_readx(address)
                aggregated_response = aggregated_response and response
                wait_mem = wait_mem or wait_mem
                if payload_words:
                    aggregated_payload = payload_words

        if wait_mem:
            caller.evict_block_passive(address)

        if aggregated_response:
            self.total_bus_invalidation_or_updates += 1
            if aggregated_payload:
                self.total_bus_traffic += aggregated_payload * 4

        return aggregated_response, aggregated_payload, wait_mem

    # for Dragon
    def send_update_req(self, caller, address):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        aggregated_payload = 0
        aggregated_response = True
        for cache in self.connected_caches:
            if cache != caller:
                response, payload_words = cache.bus_update(address)
                aggregated_response = aggregated_response and response
                if payload_words:
                    aggregated_payload = payload_words

        if aggregated_response:
            self.total_bus_invalidation_or_updates += 1
            if aggregated_payload:
                self.total_bus_traffic += 4
        return aggregated_response, aggregated_payload

    def send_lock_req(self, caller, address, lock):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        for cache in self.connected_caches:
            if cache != caller:
                cache.lock_block(address, lock)

    def check_share_line(self, caller, address):
        blocks = []
        for cache in self.connected_caches:
            if cache != caller:
                block = cache.get_cache_block(address)
                if block is not None:
                    blocks.append(block)
        return blocks
