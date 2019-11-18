import random


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
        if self.bus_master is not None:
            for _, callback in self.applicants:
                callback(False)

        if self.applicants:
            selected_index = random.randint(1, len(self.applicants)) - 1
            for i in range(len(self.applicants)):
                if i == selected_index:
                    selected_applicant, callback = self.applicants[i]
                    self.bus_master = selected_applicant
                    callback(True)
                else:
                    _, callback = self.applicants[i]
                    callback(False)

    def send_read_req(self, caller, address):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        is_blocked = False
        aggregated_payload = 0
        for cache in self.connected_caches:
            if cache != caller:
                respond, payload_words = cache.bus_read(address)
                if not respond:
                    is_blocked = True
                if payload_words:
                    aggregated_payload = payload_words

        return (not is_blocked), aggregated_payload

    def send_read_X_req(self, caller, address):
        if caller != self.bus_master:
            raise PermissionError("Requester {} is not the current bus master {}".format(caller.name,
                                                                                         self.bus_master.name))

        is_blocked = False
        aggregated_payload = 0
        for cache in self.connected_caches:
            if cache != caller:
                respond, payload_words = cache.bus_read_X(address)
                if not respond:
                    is_blocked = True
                if payload_words:
                    aggregated_payload = payload_words

        return (not is_blocked), aggregated_payload
