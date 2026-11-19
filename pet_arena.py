import copy


BASE_RATING = 1000

ADVANTAGES = {
    ("fire", "nature"),
    ("nature", "water"),
    ("water", "fire"),
}


class PetArena:
    def __init__(self, pets, config=None):
        self.config = config or {}
        self.pets = {}
        for pet_id, data in pets.items():
            pet = dict(data)
            pet.setdefault("rating", BASE_RATING)
            pet.setdefault("wins", 0)
            pet.setdefault("losses", 0)
            self.pets[pet_id] = pet
        self.queue = []
        self.history = []
        self.season = 1
        self.last_season = None

    def _power(self, pet):
        return pet["hp"] + pet["atk"] + pet["def"] + pet["speed"]

    def enqueue(self, player, pet_id, now):
        pet = self.pets.get(pet_id)
        if pet is None:
            raise ValueError("unknown pet: %s" % pet_id)
        if pet["owner"] != player:
            raise ValueError("only the owner can enqueue a pet")
        if pet_id in self.queue:
            raise ValueError("pet is already in the queue: %s" % pet_id)
        self.queue.append(pet_id)
        return None

    def matchmake(self, player, now):
        requester = None
        for pet_id in self.queue:
            if self.pets[pet_id]["owner"] == player:
                requester = pet_id
                break
        if requester is None:
            return None

        window = self.config.get("power_window", 0)
        requester_power = self._power(self.pets[requester])
        opponent = None
        for pet_id in self.queue:
            if pet_id == requester:
                continue
            candidate = self.pets[pet_id]
            if candidate["owner"] == player:
                continue
            if abs(self._power(candidate) - requester_power) <= window:
                opponent = pet_id
                break
        if opponent is None:
            return None

        self.queue.remove(requester)
        self.queue.remove(opponent)
        return {"a": requester, "b": opponent}

    def _multiplier(self, attacker_element, defender_element):
        if (attacker_element, defender_element) in ADVANTAGES:
            return 2
        return 1

    def _first_attacker(self, pet_a, pet_b):
        speed_a = self.pets[pet_a]["speed"]
        speed_b = self.pets[pet_b]["speed"]
        if speed_a == speed_b:
            return (pet_a, pet_b) if pet_a < pet_b else (pet_b, pet_a)
        return (pet_a, pet_b) if speed_a > speed_b else (pet_b, pet_a)

    def duel(self, pet_a, pet_b):
        if pet_a not in self.pets or pet_b not in self.pets or pet_a == pet_b:
            raise ValueError("duel requires two distinct registered pets")

        sides = {pet_a: dict(self.pets[pet_a]), pet_b: dict(self.pets[pet_b])}
        max_turns = self.config.get("max_turns", 12)
        first, second = self._first_attacker(pet_a, pet_b)
        order = [first, second]

        log = []
        winner = None
        attacks = 0
        while attacks < max_turns and winner is None:
            attacker_id = order[attacks % 2]
            defender_id = order[(attacks + 1) % 2]
            attacker = sides[attacker_id]
            defender = sides[defender_id]
            multiplier = self._multiplier(attacker["element"], defender["element"])
            damage = max(1, attacker["atk"] * multiplier - defender["def"])
            defender["hp"] = max(0, defender["hp"] - damage)
            attacks += 1
            log.append({"by": attacker_id, "damage": damage, "hp": defender["hp"]})
            if defender["hp"] <= 0:
                winner = attacker_id

        if winner is None:
            winner = self._judge_by_standings(sides, pet_a, pet_b)

        loser = pet_b if winner == pet_a else pet_a
        win_points = self.config.get("win_points", 30)
        loss_points = self.config.get("loss_points", 10)
        self.pets[winner]["rating"] += win_points
        self.pets[winner]["wins"] += 1
        self.pets[loser]["rating"] -= loss_points
        self.pets[loser]["losses"] += 1
        self.history.append(
            {
                "season": self.season,
                "a": pet_a,
                "b": pet_b,
                "winner": winner,
                "attacks": attacks,
                "log": copy.deepcopy(log),
            }
        )
        return {"winner": winner, "attacks": attacks, "log": log}

    def _judge_by_standings(self, sides, pet_a, pet_b):
        def ratio(pet_id):
            pet = sides[pet_id]
            return pet["hp"] / self.pets[pet_id]["hp"]

        ratio_a, ratio_b = ratio(pet_a), ratio(pet_b)
        if ratio_a != ratio_b:
            return pet_a if ratio_a > ratio_b else pet_b
        speed_a = self.pets[pet_a]["speed"]
        speed_b = self.pets[pet_b]["speed"]
        if speed_a != speed_b:
            return pet_a if speed_a > speed_b else pet_b
        return pet_a if pet_a < pet_b else pet_b

    def season_close(self, now):
        if not self.history:
            raise ValueError("cannot close a season without any duels")

        ranking = sorted(
            self.pets,
            key=lambda pet_id: (
                -self.pets[pet_id]["rating"],
                -self.pets[pet_id]["wins"],
                pet_id,
            ),
        )
        reward_table = self.config.get("season_rewards", [])
        rewards = {}
        for pet_id, reward in zip(ranking, reward_table):
            owner = self.pets[pet_id]["owner"]
            rewards[owner] = rewards.get(owner, 0) + reward

        summary = {"season": self.season, "rewards": rewards, "time": now}
        self.last_season = copy.deepcopy(summary)

        for pet in self.pets.values():
            pet["rating"] = BASE_RATING
            pet["wins"] = 0
            pet["losses"] = 0
        self.history = []
        self.season += 1
        return summary

    def state(self):
        return {
            "pets": copy.deepcopy(self.pets),
            "queue": list(self.queue),
            "history": copy.deepcopy(self.history),
            "season": self.season,
            "last_season": copy.deepcopy(self.last_season),
        }
