import random

from util import debug


class Bus:
    def __init__(self):
        self.connected_caches = []
        self.applicants = []
        self.bus_master = None

    def apply_for_bus_master(self, cache, callback):
        self.applicants.append((cache, callback))

    def release_ownership(self, caller):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))
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
        for cache in self.connected_caches:
            if cache != caller:
                response, payload_words = cache.bus_read(address)
                aggregated_response = aggregated_response and response
                if payload_words:
                    aggregated_payload = payload_words

        return aggregated_response, aggregated_payload

    def send_read_X_req(self, caller, address):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        aggregated_payload = 0
        aggregated_response = True
        for cache in self.connected_caches:
            if cache != caller:
                response, payload_words = cache.bus_readx(address)
                aggregated_response = aggregated_response and response
                if payload_words:
                    aggregated_payload = payload_words

        return aggregated_response, aggregated_payload

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

        return aggregated_response, aggregated_payload

    def send_lock_req(self, caller, address, lock):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        for cache in self.connected_caches:
            if cache != caller:
                cache.lock_block(address, lock)


