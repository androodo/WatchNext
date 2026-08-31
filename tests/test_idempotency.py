from __future__ import annotations

from datetime import UTC, datetime

from watchnext.common.schema import new_event
from watchnext.online.processor import FeatureProcessor, MemoryRedis


def test_duplicate_event_id_does_not_double_count():
    redis = MemoryRedis()
    proc = FeatureProcessor(redis, item_categories={"10": ["sci_fi"]})
    ev = new_event("42", "10", "like", timestamp=datetime.now(UTC), event_id="abc123")
    first = proc.process_event(ev)
    second = proc.process_event(ev)
    assert first.status == "applied"
    assert second.status == "duplicate"
    assert first.state is not None
    assert first.state.likes_24h == 1
    assert first.state.interaction_count == 1
    # Features remain at the first-apply values.
    import json

    stored = json.loads(redis.get("user:42:features") or "{}")
    assert stored["likes_24h"] == 1
    assert stored["interaction_count"] == 1


def test_invalid_payload_is_rejected():
    proc = FeatureProcessor(MemoryRedis(), item_categories={})
    result = proc.process_payload({"user_id": "1"})
    assert result.status == "invalid"


def test_live_title_uses_metadata_categories():
    proc = FeatureProcessor(MemoryRedis(), item_categories={})
    ev = new_event(
        "guest",
        "tt3581920",
        "like",
        timestamp=datetime.now(UTC),
        event_id="live-1",
        metadata={"title": "The Odyssey (2026)", "categories": ["adventure", "fantasy"]},
    )
    result = proc.process_event(ev)
    assert result.status == "applied"
    assert result.state is not None
    assert result.state.affinity("adventure") > 0
    assert result.state.affinity("fantasy") > 0


def test_empty_affinities_seed_from_liked_catalog():
    redis = MemoryRedis()
    proc = FeatureProcessor(redis, item_categories={"tt1": ["sci_fi"], "tt2": ["action"]})
    redis.set(
        "user:guest:features",
        '{"liked_items": ["tt1", "tt2"], "affinities": {}, "recent_actions": []}',
    )
    assert proc.backfill_user_affinities("user:guest:features") is True
    import json

    stored = json.loads(redis.get("user:guest:features") or "{}")
    assert stored["affinities"]["sci_fi"] > 0
    assert stored["affinities"]["action"] > 0
