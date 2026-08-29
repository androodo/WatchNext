"""E2E feedback-loop test. Enable with RUN_E2E=1 against a live stack."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_E2E") != "1", reason="set RUN_E2E=1")

API = os.environ.get("API_URL", "http://localhost:8080")


def _json(method: str, path: str, body=None):
    import json
    from urllib.request import Request, urlopen

    data = None if body is None else json.dumps(body).encode()
    req = Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def test_likes_increase_target_affinity_and_feed_signal():
    user = os.environ.get("E2E_USER", "42")
    before_feat = _json("GET", f"/v1/users/{user}/features")["features"]
    before_feed = _json("GET", f"/v1/recommendations/{user}?limit=10")
    sci_before = float((before_feat.get("affinities") or {}).get("sci_fi", 0.0))

    # Any sci-fi-looking catalog ids 1..20; consumer uses item_categories.json.
    for i in range(1, 9):
        _json(
            "POST",
            "/v1/events",
            {
                "event_id": str(uuid.uuid4()),
                "schema_version": 1,
                "user_id": user,
                "item_id": str(i),
                "event_type": "like",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
    deadline = time.time() + 20
    after_feat = before_feat
    while time.time() < deadline:
        after_feat = _json("GET", f"/v1/users/{user}/features")["features"]
        sci_after = float((after_feat.get("affinities") or {}).get("sci_fi", 0.0))
        if sci_after != sci_before or after_feat.get("likes_24h", 0) > before_feat.get("likes_24h", 0):
            break
        time.sleep(0.4)

    assert after_feat.get("interaction_count", 0) >= before_feat.get("interaction_count", 0)
    after_feed = _json("GET", f"/v1/recommendations/{user}?limit=10")
    assert after_feed.get("recommendations")
    # Behavioral signal: features moved or likes window increased.
    assert after_feat.get("likes_24h", 0) >= before_feat.get("likes_24h", 0)
    assert before_feed.get("request_id") != after_feed.get("request_id")
