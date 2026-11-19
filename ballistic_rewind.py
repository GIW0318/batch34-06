class BallisticRewind:
    def __init__(self, config=None):
        self.config = config or {}

    def record(self, t, positions):
        return None

    def fire(self, shooter, target, origin, direction, speed, now, latency=0):
        return None

    def validate_replay(self, shots):
        return None

    def state(self):
        return {}
