import pytest

import pet_arena as pa

PETS = {
    "ember": {"owner": "alice", "element": "fire", "hp": 30, "atk": 8, "def": 2, "speed": 5},
    "moss": {"owner": "bob", "element": "nature", "hp": 30, "atk": 8, "def": 2, "speed": 4},
    "tide": {"owner": "carol", "element": "water", "hp": 40, "atk": 5, "def": 3, "speed": 6},
    "shell": {"owner": "dave", "element": "water", "hp": 50, "atk": 2, "def": 9, "speed": 1},
    "frost": {"owner": "alice", "element": "water", "hp": 25, "atk": 6, "def": 1, "speed": 7},
}
CONFIG = {
    "power_window": 10,
    "max_turns": 12,
    "win_points": 30,
    "loss_points": 10,
    "season_rewards": [300, 150, 50],
}


def arena(**cfg):
    base = dict(CONFIG)
    base.update(cfg)
    pets = {
        pid: {
            "owner": v["owner"],
            "element": v["element"],
            "hp": v["hp"],
            "atk": v["atk"],
            "def": v["def"],
            "speed": v["speed"],
        }
        for pid, v in PETS.items()
    }
    return pa.PetArena(pets, base)


def test_enqueue_requires_owner():
    a = arena()
    with pytest.raises(ValueError):
        a.enqueue("bob", "ember", 0)


def test_enqueue_unknown_pet_rejected():
    a = arena()
    with pytest.raises(ValueError):
        a.enqueue("alice", "ghost", 0)


def test_duplicate_enqueue_rejected():
    a = arena()
    a.enqueue("alice", "ember", 0)
    with pytest.raises(ValueError):
        a.enqueue("alice", "ember", 1)


def test_matchmake_pairs_near_power():
    a = arena()
    a.enqueue("alice", "ember", 0)
    a.enqueue("bob", "moss", 1)
    res = a.matchmake("alice", 2)
    assert res["a"] == "ember"
    assert res["b"] == "moss"
    assert a.state()["queue"] == []


def test_matchmake_respects_power_window():
    a = arena()
    a.enqueue("alice", "frost", 0)
    a.enqueue("dave", "shell", 1)
    assert a.state()["queue"] == ["frost", "shell"]
    assert a.matchmake("alice", 2) is None


def test_matchmake_skips_same_owner():
    a = arena()
    a.enqueue("alice", "ember", 0)
    a.enqueue("alice", "frost", 1)
    assert len(a.state()["queue"]) == 2
    assert a.matchmake("alice", 2) is None
    a.enqueue("bob", "moss", 3)
    res = a.matchmake("alice", 4)
    assert res["a"] == "ember"
    assert res["b"] == "moss"


def test_matchmake_without_candidates_returns_none():
    a = arena()
    a.enqueue("alice", "ember", 0)
    assert a.state()["queue"] == ["ember"]
    assert a.matchmake("alice", 1) is None


def test_element_advantage_doubles_damage():
    a = arena()
    res = a.duel("ember", "moss")
    assert res["winner"] == "ember"
    assert res["attacks"] == 5
    assert res["log"][0]["damage"] == 14
    assert res["log"][0]["hp"] == 16


def test_turn_order_and_minimum_damage():
    a = arena()
    res = a.duel("tide", "shell")
    first = res["log"][0]
    assert first["by"] == "tide"
    assert first["damage"] == 1


def test_duel_updates_ratings():
    a = arena()
    a.duel("ember", "moss")
    st = a.state()
    assert st["pets"]["ember"]["rating"] == 1030
    assert st["pets"]["moss"]["rating"] == 990
    assert st["pets"]["ember"]["wins"] == 1
    assert st["pets"]["moss"]["losses"] == 1
    assert len(st["history"]) == 1


def test_duel_rejects_bad_pets():
    a = arena()
    with pytest.raises(ValueError):
        a.duel("ember", "ember")
    with pytest.raises(ValueError):
        a.duel("ember", "ghost")


def test_season_rewards_top_ranked_owners():
    a = arena()
    a.duel("ember", "moss")
    a.season_close(10)
    assert a.state()["last_season"]["rewards"] == {"alice": 450, "dave": 50}


def test_season_close_resets_standings():
    a = arena()
    a.duel("ember", "moss")
    a.season_close(10)
    st = a.state()
    assert st["season"] == 2
    assert st["pets"]["ember"]["rating"] == 1000
    assert st["pets"]["ember"]["wins"] == 0
    assert st["pets"]["moss"]["losses"] == 0
    assert st["history"] == []


def test_season_close_needs_duels():
    a = arena()
    with pytest.raises(ValueError):
        a.season_close(0)
    a.duel("ember", "moss")
    a.season_close(1)
    with pytest.raises(ValueError):
        a.season_close(2)


def test_state_is_detached():
    a = arena()
    a.enqueue("alice", "ember", 0)
    st = a.state()
    st["pets"]["ember"]["hp"] = 1
    st["queue"].append("moss")
    assert a.state()["pets"]["ember"]["hp"] == 30
    assert a.state()["queue"] == ["ember"]
