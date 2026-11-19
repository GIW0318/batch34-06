import copy

LEADER = "leader"
OFFICER = "officer"
MEMBER = "member"
VALID_RANKS = (LEADER, OFFICER, MEMBER)
OPEN_RANKS = (LEADER, OFFICER)


class GuildRaidLedger:
    def __init__(self, guilds, raids, config=None):
        self.guilds = copy.deepcopy(guilds)
        self.raids = copy.deepcopy(raids)
        self.config = dict(config or {})
        self._cut_bps = self.config.get("guild_cut_bps", 0)
        self._lockout_span = self.config.get("lockout", 0)
        self._min_damage = self.config.get("min_damage", 0)
        self._runtime = {
            raid_id: {
                "status": None,
                "hp": cfg["hp"],
                "damage": {},
                "settled": {},
                "participants": set(),
            }
            for raid_id, cfg in self.raids.items()
        }
        self._lockouts = {}

    def recruit(self, guild_id, player, now=0):
        guild = self.guilds.get(guild_id)
        if guild is None:
            raise ValueError(f"unknown guild: {guild_id}")
        if player in guild["members"]:
            raise ValueError(f"player already recruited: {player}")
        guild["members"][player] = MEMBER
        return None

    def set_rank(self, guild_id, actor, player, rank):
        guild = self.guilds.get(guild_id)
        if guild is None:
            raise ValueError(f"unknown guild: {guild_id}")
        if guild["members"].get(actor) != LEADER:
            raise ValueError(f"actor is not the guild leader: {actor}")
        if player not in guild["members"]:
            raise ValueError(f"unknown member: {player}")
        if rank not in VALID_RANKS:
            raise ValueError(f"unknown rank: {rank}")
        guild["members"][player] = rank
        return None

    def open_raid(self, raid_id, player, now):
        cfg = self.raids.get(raid_id)
        if cfg is None:
            raise ValueError(f"unknown raid: {raid_id}")
        runtime = self._runtime[raid_id]
        if runtime["status"] is not None:
            raise ValueError(f"raid already opened: {raid_id}")
        guild = self.guilds.get(cfg["guild"])
        if guild is None:
            raise ValueError(f"unknown guild: {cfg['guild']}")
        if guild["members"].get(player) not in OPEN_RANKS:
            raise ValueError(f"player cannot open raid: {player}")
        runtime["status"] = "open"
        runtime["hp"] = cfg["hp"]
        return None

    def engage(self, raid_id, player, amount, now):
        cfg = self.raids.get(raid_id)
        if cfg is None:
            raise ValueError(f"unknown raid: {raid_id}")
        runtime = self._runtime[raid_id]
        if runtime["status"] != "open":
            raise ValueError(f"raid is not open: {raid_id}")
        if amount < 0:
            raise ValueError("damage amount must be non-negative")
        guild = self.guilds.get(cfg["guild"])
        if guild is None or player not in guild["members"]:
            raise ValueError(f"player is not a guild member: {player}")
        locked_until = self._lockouts.get((cfg["guild"], cfg["group"], player))
        if locked_until is not None and now < locked_until:
            raise ValueError(f"player is locked out: {player}")
        dealt = min(amount, runtime["hp"])
        runtime["hp"] -= dealt
        runtime["damage"][player] = runtime["damage"].get(player, 0) + dealt
        runtime["participants"].add(player)
        if runtime["hp"] == 0:
            runtime["status"] = "cleared"
        return dealt

    def settle(self, raid_id, now):
        cfg = self.raids.get(raid_id)
        if cfg is None:
            raise ValueError(f"unknown raid: {raid_id}")
        runtime = self._runtime[raid_id]
        if runtime["status"] != "cleared":
            raise ValueError(f"raid is not cleared: {raid_id}")

        guild_id = cfg["guild"]
        pool = cfg["pool"]
        cut = pool * self._cut_bps // 10000
        self.guilds[guild_id]["gold"] += cut
        distributable = pool - cut

        damage = runtime["damage"]
        participants = runtime["participants"]
        total_damage = sum(damage.values())
        payouts = {name: 0 for name in sorted(participants)}
        if total_damage > 0:
            for name in payouts:
                if damage[name] >= self._min_damage:
                    payouts[name] = distributable * damage[name] // total_damage
            leftover = distributable - sum(payouts.values())
            if leftover > 0:
                eligible = [
                    name for name in participants
                    if damage[name] >= self._min_damage
                ]
                if eligible:
                    top = min(eligible, key=lambda name: (-damage[name], name))
                    payouts[top] += leftover
                else:
                    self.guilds[guild_id]["gold"] += leftover

        runtime["settled"] = payouts
        runtime["status"] = "settled"
        locked_until = now + self._lockout_span
        for name in participants:
            self._lockouts[(guild_id, cfg["group"], name)] = locked_until
        return copy.deepcopy(payouts)

    def state(self):
        return {
            "guilds": {
                guild_id: {
                    "members": dict(guild["members"]),
                    "gold": guild["gold"],
                }
                for guild_id, guild in self.guilds.items()
            },
            "raids": {
                raid_id: {
                    "status": runtime["status"],
                    "hp": runtime["hp"],
                    "damage": dict(runtime["damage"]),
                    "settled": dict(runtime["settled"]),
                }
                for raid_id, runtime in self._runtime.items()
            },
        }
