class SpawnContract:
    def __init__(self, zones, contracts, players, config=None):
        self.zones = zones
        self.contracts = contracts
        self.players = players
        self.config = config or {}

    def tick(self, now):
        return None

    def direct(self, zone, now):
        return None

    def sign(self, player, contract_id, now):
        return None

    def slay(self, player, unit_id, now):
        return None

    def claim(self, player, contract_id, now):
        return None

    def state(self):
        return {}
