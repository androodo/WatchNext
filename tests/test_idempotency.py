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
