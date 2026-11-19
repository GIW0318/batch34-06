import pytest

import ballistic_rewind as br


def rewind(**cfg):
    base = {"history": 100, "max_rewind": 50, "radius": 1.0}
    base.update(cfg)
    return br.BallisticRewind(base)


def recorded():
    b = rewind()
    b.record(0, {"alice": (0, 0), "bob": (10, 0)})
    b.record(10, {"alice": (0, 0), "bob": (20, 0)})
    b.record(20, {"alice": (0, 0), "bob": (10, 5)})
    b.record(40, {"alice": (0, 0), "bob": (10, 1)})
    return b


def test_record_appends_frames():
    b = rewind()
    b.record(0, {"bob": (0, 0)})
    b.record(10, {"bob": (5, 0)})
    frames = b.state()["frames"]
    assert [f["t"] for f in frames] == [0, 10]
    assert frames[1]["positions"]["bob"] == [5, 0]


def test_record_rejects_backwards_time():
    b = rewind()
    b.record(10, {"bob": (5, 0)})
    with pytest.raises(ValueError):
        b.record(9, {"bob": (4, 0)})


def test_record_same_time_replaces_frame():
    b = rewind()
    b.record(10, {"bob": (5, 0)})
    b.record(10, {"bob": (9, 9)})
    frames = b.state()["frames"]
    assert len(frames) == 2
    assert frames[1]["positions"]["bob"] == [9, 9]


def test_fire_hits_rewound_position():
    b = recorded()
    res = b.fire("alice", "bob", (0, 0), (1, 0), 10, now=30, latency=20)
    assert res["hit"] is True
    assert res["reason"] is None
    assert res["rewound"] == 10
    assert res["travel"] == pytest.approx(2.0)
    assert res["impact"] == pytest.approx((20.0, 0.0))


def test_direction_length_is_ignored():
    b = recorded()
    res = b.fire("alice", "bob", (0, 0), (2, 0), 10, now=30, latency=20)
    assert res["hit"] is True
    assert res["travel"] == pytest.approx(2.0)
    assert res["impact"] == pytest.approx((20.0, 0.0))


def test_fire_misses_when_perpendicular_too_large():
    b = recorded()
    res = b.fire("alice", "bob", (0, 0), (1, 0), 10, now=30, latency=10)
    assert res["hit"] is False
    assert res["reason"] == "distance"
    assert res["rewound"] == 20


def test_fire_behind_origin_misses():
    b = recorded()
    res = b.fire("alice", "bob", (0, 0), (-1, 0), 10, now=30, latency=20)
    assert res["hit"] is False
    assert res["reason"] == "behind"


def test_fire_without_history_reports_expired():
    b = rewind()
    b.record(100, {"bob": (1, 0)})
    res = b.fire("alice", "bob", (0, 0), (1, 0), 10, now=50, latency=0)
    assert res["hit"] is False
    assert res["reason"] == "no_history"
    assert res["rewound"] is None


def test_fire_radius_boundary_counts_as_hit():
    b = recorded()
    res = b.fire("alice", "bob", (0, 0), (1, 0), 10, now=50, latency=10)
    assert res["hit"] is True
    assert res["travel"] == pytest.approx(1.0)
    assert res["impact"] == pytest.approx((10.0, 0.0))


def test_fire_rejects_bad_direction_and_speed():
    b = recorded()
    with pytest.raises(ValueError):
        b.fire("alice", "bob", (0, 0), (0, 0), 10, now=30, latency=10)
    with pytest.raises(ValueError):
        b.fire("alice", "bob", (0, 0), (1, 0), 0, now=30, latency=10)


def test_fire_rejects_bad_latency():
    b = recorded()
    with pytest.raises(ValueError):
        b.fire("alice", "bob", (0, 0), (1, 0), 10, now=30, latency=51)
    with pytest.raises(ValueError):
        b.fire("alice", "bob", (0, 0), (1, 0), 10, now=30, latency=-1)


def test_validate_replay_accepts_consistent_shot():
    b = recorded()
    shot = {
        "target": "bob",
        "origin": (0, 0),
        "direction": (1, 0),
        "speed": 10,
        "now": 30,
        "latency": 20,
        "hit": True,
    }
    res = b.validate_replay([shot])
    assert res["ok"] is True
    assert res["mismatches"] == []
    assert res["checked"] == 1


def test_validate_replay_flags_tampered_result():
    b = recorded()
    shot = {
        "target": "bob",
        "origin": (0, 0),
        "direction": (1, 0),
        "speed": 10,
        "now": 30,
        "latency": 20,
        "hit": False,
    }
    res = b.validate_replay([shot])
    assert res["ok"] is False
    assert res["mismatches"] == [0]


def test_validate_replay_flags_expired_claim():
    b = rewind()
    b.record(100, {"bob": (1, 0)})
    shot = {
        "target": "bob",
        "origin": (0, 0),
        "direction": (1, 0),
        "speed": 10,
        "now": 5,
        "latency": 0,
        "hit": True,
    }
    res = b.validate_replay([shot])
    assert res["ok"] is False
    assert res["mismatches"] == [0]


def test_state_is_detached():
    b = recorded()
    b.fire("alice", "bob", (0, 0), (1, 0), 10, now=30, latency=20)
    st = b.state()
    st["frames"][0]["positions"]["bob"][0] = 999
    st["shots"][0]["hit"] = False
    fresh = b.state()
    assert fresh["frames"][0]["positions"]["bob"][0] == 10
    assert fresh["shots"][0]["hit"] is True
    assert len(fresh["frames"]) == 4
