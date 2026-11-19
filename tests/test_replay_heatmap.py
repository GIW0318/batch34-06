import pytest

import replay_heatmap as rh

REPLAYS = {
    "r1": {
        "recorded_at": 0,
        "duration": 40,
        "ticks": [0, 10, 20, 30, 40],
        "events": [
            {"t": 5, "x": 2, "y": 2},
            {"t": 12, "x": 7, "y": 7},
            {"t": 15, "x": 9, "y": 1},
            {"t": 25, "x": 5, "y": 5},
            {"t": 35, "x": 1, "y": 9},
        ],
    },
    "r2": {
        "recorded_at": 50,
        "duration": 20,
        "ticks": [0, 10, 20],
        "events": [
            {"t": 2, "x": 3, "y": 3},
            {"t": 18, "x": 8, "y": 8},
        ],
    },
}
REGIONS = {"base": (0, 0, 5, 5), "mid": (5, 0, 10, 10)}
CONFIG = {"max_bookmarks": 2, "bookmark_ttl": 30, "replay_ttl": 100, "count_unknown": True}


def archive(**cfg):
    base = dict(CONFIG)
    base.update(cfg)
    replays = {}
    for rid, v in REPLAYS.items():
        replays[rid] = {
            "recorded_at": v["recorded_at"],
            "duration": v["duration"],
            "ticks": list(v["ticks"]),
            "events": [dict(e) for e in v["events"]],
        }
    return rh.ReplayHeatmap(replays, base)


def test_seek_returns_previous_tick():
    res = archive().seek("r1", 17)
    assert res["tick"] == 10
    assert res["t"] == 17
    assert res["exact"] is False
    assert res["next"] == 20
    assert archive().seek("r1", 10)["exact"] is True


def test_seek_clamps_past_duration():
    res = archive().seek("r1", 99)
    assert res["t"] == 40
    assert res["tick"] == 40
    assert res["next"] is None


def test_seek_rejects_bad_arguments():
    a = archive()
    with pytest.raises(ValueError):
        a.seek("r1", -1)
    with pytest.raises(ValueError):
        a.seek("zz", 5)


def test_bookmark_records_expiry():
    a = archive()
    bm = a.bookmark("r1", "b1", 10, "hook", "alice", now=5)
    assert bm["expires"] == 35
    assert a.bookmarks("r1", 6)[0]["t"] == 10
    assert a.bookmarks("r1", 6)[0]["player"] == "alice"


def test_duplicate_bookmark_id_rejected():
    a = archive()
    a.bookmark("r1", "b1", 10, "hook", "alice", 0)
    with pytest.raises(ValueError):
        a.bookmark("r2", "b1", 5, "again", "bob", 1)


def test_bookmark_bad_time_or_note_rejected():
    a = archive()
    with pytest.raises(ValueError):
        a.bookmark("r1", "b1", 41, "late", "alice", 0)
    with pytest.raises(ValueError):
        a.bookmark("r1", "b1", -1, "early", "alice", 0)
    with pytest.raises(ValueError):
        a.bookmark("r1", "b1", 5, "   ", "alice", 0)


def test_bookmark_cap_per_player():
    a = archive()
    a.bookmark("r1", "b1", 10, "one", "alice", 0)
    a.bookmark("r1", "b2", 20, "two", "alice", 1)
    with pytest.raises(ValueError):
        a.bookmark("r1", "b3", 30, "three", "alice", 2)
    a.bookmark("r2", "b4", 5, "other", "bob", 3)


def test_expired_bookmarks_hidden():
    a = archive()
    a.bookmark("r1", "b1", 10, "hook", "alice", now=5)
    assert len(a.bookmarks("r1", 34)) == 1
    assert a.bookmarks("r1", 35) == []


def test_remove_bookmark_requires_owner():
    a = archive()
    a.bookmark("r1", "b1", 10, "hook", "alice", 0)
    with pytest.raises(ValueError):
        a.remove_bookmark("bob", "b1")
    with pytest.raises(ValueError):
        a.remove_bookmark("alice", "b9")
    a.remove_bookmark("alice", "b1")
    assert a.bookmarks("r1", 1) == []


def test_heatmap_counts_named_regions():
    assert archive().heatmap("r1", REGIONS) == {"base": 1, "mid": 3, "unknown": 1}


def test_heatmap_can_skip_unknown():
    a = archive(count_unknown=False)
    assert a.heatmap("r1", REGIONS) == {"base": 1, "mid": 3}


def test_heatmap_filters_time_window():
    assert archive().heatmap("r1", REGIONS, window=(10, 20)) == {"base": 0, "mid": 2}


def test_heatmap_aggregates_replays():
    assert archive().heatmap(None, REGIONS) == {"base": 2, "mid": 4, "unknown": 1}


def test_prune_removes_expired_data():
    a = archive()
    a.bookmark("r1", "b1", 10, "hook", "alice", now=0)
    removed = a.prune(120)
    assert removed["replays"] == ["r1"]
    assert removed["bookmarks"] == ["b1"]
    assert set(a.state()["replays"]) == {"r2"}
    with pytest.raises(ValueError):
        a.seek("r1", 5)


def test_state_is_detached():
    a = archive()
    a.bookmark("r1", "b1", 10, "hook", "alice", now=0)
    st = a.state()
    st["replays"]["r1"]["events"].append({"t": 1, "x": 0, "y": 0})
    st["bookmarks"]["b1"]["note"] = "edited"
    fresh = a.state()
    assert len(fresh["replays"]["r1"]["events"]) == 5
    assert fresh["bookmarks"]["b1"]["note"] == "hook"
