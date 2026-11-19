class ReplayHeatmap:
    def __init__(self, replays, config=None):
        self.replays = replays
        self.config = config or {}

    def seek(self, replay_id, t):
        return None

    def bookmark(self, replay_id, bookmark_id, t, note, player, now):
        return None

    def bookmarks(self, replay_id, now):
        return []

    def remove_bookmark(self, player, bookmark_id):
        return None

    def heatmap(self, replay_id, regions, window=None):
        return {}

    def prune(self, now):
        return None

    def state(self):
        return {}
