from __future__ import annotations

from datetime import UTC, datetime, timedelta

from watchnext.common.schema import new_event
from watchnext.features.engine import FeatureEngine


def test_event_validation_rejects_unknown_type():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        new_event("1", "2", "explode")


def test_ema_affinity_increases_for_likes():
    eng = FeatureEngine()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    for i in range(3):
        ev = new_event("u", "sci-1", "like", timestamp=t0 + timedelta(seconds=i), event_id=str(i))
        state = eng.apply(ev, ["sci_fi"])
    assert state.affinity("sci_fi") > 0.3
    assert state.likes_24h == 3
    assert state.interaction_count == 3


def test_skip_reduces_comedy_affinity():
    eng = FeatureEngine()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    eng.apply(new_event("u", "c1", "like", timestamp=t0, event_id="a"), ["comedy"])
    before = eng.snapshot(t0).affinity("comedy")
    after = eng.apply(
        new_event("u", "c2", "skip", timestamp=t0 + timedelta(seconds=1), event_id="b"),
        ["comedy"],
    )
    assert after.affinity("comedy") < before


def test_impressions_do_not_change_affinity():
    eng = FeatureEngine()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    eng.apply(new_event("u", "1", "impression", timestamp=t0, event_id="i"), ["drama"])
    state = eng.snapshot(t0)
    assert state.affinities == {}
    assert state.interaction_count == 0


def test_windowed_counts_respect_as_of():
    eng = FeatureEngine()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    old = t0 - timedelta(days=10)
    eng.apply(new_event("u", "1", "like", timestamp=old, event_id="old"), ["x"])
    eng.apply(new_event("u", "2", "like", timestamp=t0, event_id="new"), ["x"])
    snap = eng.snapshot(t0)
    assert snap.likes_24h == 1
    assert snap.likes_7d == 1
    assert snap.interaction_count == 2


def test_liked_items_persist_and_skip_removes_them():
    eng = FeatureEngine()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    like = new_event("u", "10", "like", timestamp=t0, event_id="l", metadata={"title": "Gladiator (2000)"})
    state = eng.apply(like, ["action"])
    assert state.liked_items == ["10"]
    assert state.recent_actions[-1]["title"] == "Gladiator (2000)"
    after = eng.apply(
        new_event("u", "10", "skip", timestamp=t0 + timedelta(seconds=1), event_id="s"),
        ["action"],
    )
    assert after.liked_items == []
    assert "10" in after.disliked_items


def test_seed_affinities_from_existing_likes():
    eng = FeatureEngine(liked_items=["tt1", "tt2"])
    eng.seed_affinities_from_likes({"tt1": ["sci_fi"], "tt2": ["action"]})
    snap = eng.snapshot(datetime(2020, 1, 1, tzinfo=UTC))
    assert snap.affinity("sci_fi") > 0
    assert snap.affinity("action") > 0
