class PetArena:
    def __init__(self, pets, config=None):
        self.pets = pets
        self.config = config or {}

    def enqueue(self, player, pet_id, now):
        return None

    def matchmake(self, player, now):
        return None

    def duel(self, pet_a, pet_b):
        return None

    def season_close(self, now):
        return None

    def state(self):
        return {}
