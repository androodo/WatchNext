#!/usr/bin/env python
"""DEMO 4: publish the same event_id twice; Redis counters must not double."""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "http://localhost:8080"


def http_json(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    user_id = sys.argv[1] if len(sys.argv) > 1 else "42"
    before = http_json("GET", f"/v1/users/{user_id}/features")["features"]
    event_id = str(uuid.uuid4())
    payload = {
        "event_id": event_id,
        "schema_version": 1,
        "user_id": user_id,
        "item_id": "1",
        "event_type": "like",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    http_json("POST", "/v1/events", payload)
    http_json("POST", "/v1/events", payload)
    time.sleep(2)
    after = http_json("GET", f"/v1/users/{user_id}/features")["features"]
    delta = int(after.get("likes_24h", 0)) - int(before.get("likes_24h", 0))
    print("event_id", event_id)
    print("likes_24h before", before.get("likes_24h"), "after", after.get("likes_24h"), "delta", delta)
    if delta > 1:
        raise SystemExit("FAIL: duplicate event incremented likes more than once")
    print("PASS: at-least-once delivery did not double-count (delta <= 1)")


if __name__ == "__main__":
    main()
