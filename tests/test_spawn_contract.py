import pytest

import spawn_contract as sc

ZONES = {
    "cave": {
        "budget": 5,
        "cap": 9,
        "regen": 1,
        "wave": ["rat", "rat"],
        "monsters": {
            "rat": {"cost": 2, "loot": {"fang": 1}},
            "bat": {"cost": 3, "loot": {"wing": 1}},
        },
    },
    "nest": {
        "budget": 1,
        "cap": 4,
        "regen": 2,
        "wave": ["ant", "ant", "ant"],
        "monsters": {"ant": {"cost": 1, "loot": {}}},
    },
}
CONTRACTS = {
    "c1": {"zone": "cave", "monster": "rat", "count": 2, "gold": 50, "items": {"gem": 1}, "deadline": 100},
    "c2": {"zone": "nest", "monster": "ant", "count": 1, "gold": 20, "items": {}, "deadline": 100},
}
PLAYERS = {"alice": {"gold": 0, "items": {}}, "bob": {"gold": 0, "items": {}}}


def game(**cfg):
    base = {"max_contracts": 2}
    base.update(cfg)
    zones = {}
    for zid, v in ZONES.items():
        zones[zid] = {
            "budget": v["budget"],
            "cap": v["cap"],
            "regen": v["regen"],
            "wave": list(v["wave"]),
            "monsters": {
                m: {"cost": d["cost"], "loot": dict(d["loot"])}
                for m, d in v["monsters"].items()
            },
        }
    contracts = {
        cid: {
            "zone": c["zone"],
            "monster": c["monster"],
            "count": c["count"],
            "gold": c["gold"],
            "items": dict(c["items"]),
            "deadline": c["deadline"],
        }
        for cid, c in CONTRACTS.items()
    }
    players = {p: {"gold": v["gold"], "items": dict(v["items"])} for p, v in PLAYERS.items()}
    return sc.SpawnContract(zones, contracts, players, base)


def test_direct_spawns_wave_and_spends_budget():
    g = game()
    ids = g.direct("cave", 0)
    assert ids == ["cave-1", "cave-2"]
    st = g.state()
    assert st["zones"]["cave"]["budget"] == 1
    assert st["zones"]["cave"]["alive"] == ["cave-1", "cave-2"]


def test_direct_rejects_when_budget_short():
    g = game()
    with pytest.raises(ValueError):
        g.direct("nest", 0)
    st = g.state()
    assert st["zones"]["nest"]["budget"] == 1
    assert st["zones"]["nest"]["alive"] == []


def test_tick_regenerates_budget_with_cap():
    g = game()
    g.tick(1)
    assert g.state()["zones"]["nest"]["budget"] == 3
    g.tick(100)
    assert g.state()["zones"]["nest"]["budget"] == 4


def test_tick_rejects_backwards_time():
    g = game()
    g.tick(10)
    with pytest.raises(ValueError):
        g.tick(9)


def test_slay_drops_loot():
    g = game()
    g.direct("cave", 0)
    g.slay("alice", "cave-1", 1)
    st = g.state()
    assert st["players"]["alice"]["items"]["fang"] == 1
    assert st["zones"]["cave"]["alive"] == ["cave-2"]


def test_slay_unknown_unit_rejected():
    g = game()
    with pytest.raises(ValueError):
        g.slay("alice", "cave-9", 1)


def test_sign_unknown_contract_rejected():
    g = game()
    with pytest.raises(ValueError):
        g.sign("alice", "c9", 0)


def test_duplicate_sign_rejected():
    g = game()
    g.sign("alice", "c1", 0)
    with pytest.raises(ValueError):
        g.sign("alice", "c1", 1)


def test_sign_past_deadline_rejected():
    g = game()
    with pytest.raises(ValueError):
        g.sign("alice", "c1", 150)


def test_kill_credits_matching_contract_only():
    g = game()
    g.sign("alice", "c1", 0)
    g.tick(1)
    g.direct("nest", 1)
    g.slay("alice", "nest-1", 2)
    assert g.state()["players"]["alice"]["contracts"]["c1"]["progress"] == 0
    g.direct("cave", 2)
    g.slay("alice", "cave-1", 3)
    assert g.state()["players"]["alice"]["contracts"]["c1"]["progress"] == 1


def test_progress_stops_at_required_count():
    g = game()
    g.sign("alice", "c1", 0)
    g.direct("cave", 0)
    g.tick(4)
    g.direct("cave", 4)
    g.slay("alice", "cave-1", 5)
    g.slay("alice", "cave-2", 6)
    g.slay("alice", "cave-3", 7)
    assert g.state()["players"]["alice"]["contracts"]["c1"]["progress"] == 2


def test_claim_before_complete_rejected():
    g = game()
    g.sign("alice", "c1", 0)
    g.direct("cave", 1)
    g.slay("alice", "cave-1", 2)
    with pytest.raises(ValueError):
        g.claim("alice", "c1", 3)


def test_claim_pays_gold_and_items():
    g = game()
    g.sign("alice", "c1", 0)
    g.direct("cave", 1)
    g.slay("alice", "cave-1", 2)
    g.slay("alice", "cave-2", 3)
    g.claim("alice", "c1", 10)
    st = g.state()
    assert st["players"]["alice"]["gold"] == 50
    assert st["players"]["alice"]["items"] == {"fang": 2, "gem": 1}
    assert st["players"]["alice"]["contracts"]["c1"]["status"] == "completed"


def test_claim_twice_rejected():
    g = game()
    g.sign("alice", "c1", 0)
    g.direct("cave", 1)
    g.slay("alice", "cave-1", 2)
    g.slay("alice", "cave-2", 3)
    g.claim("alice", "c1", 10)
    with pytest.raises(ValueError):
        g.claim("alice", "c1", 11)


def test_state_is_detached():
    g = game()
    g.sign("alice", "c1", 0)
    g.direct("cave", 0)
    st = g.state()
    st["players"]["alice"]["contracts"]["c1"]["progress"] = 99
    st["zones"]["cave"]["alive"].append("cave-9")
    fresh = g.state()
    assert fresh["players"]["alice"]["contracts"]["c1"]["progress"] == 0
    assert fresh["zones"]["cave"]["alive"] == ["cave-1", "cave-2"]
