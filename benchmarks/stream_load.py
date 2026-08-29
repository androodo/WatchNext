#!/usr/bin/env python
"""Streaming benchmark: N interactions through the API → consumer → Redis."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("API_URL", "http://localhost:8080")
N = int(os.environ.get("STREAM_N", "1000"))
USER = os.environ.get("BENCH_USER", "42")


def post_event(i: int) -> None:
    payload = {
        "event_id": str(uuid.uuid4()),
        "schema_version": 1,
        "user_id": USER,
        "item_id": str((i % 50) + 1),
        "event_type": "view",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    req = Request(
        f"{API}/v1/events",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=5) as resp:
        if resp.status >= 300:
            raise RuntimeError(resp.status)


def features() -> dict:
    with urlopen(f"{API}/v1/users/{USER}/features", timeout=5) as resp:
        return json.loads(resp.read().decode())["features"]


def main() -> None:
    before = features()
    t0 = time.perf_counter()
    for i in range(N):
        post_event(i)
    publish_s = time.perf_counter() - t0
    target = int(before.get("interaction_count", 0)) + N
    deadline = time.time() + 60
    last = before
    while time.time() < deadline:
        last = features()
        if int(last.get("interaction_count", 0)) >= target:
            break
        time.sleep(0.1)
    total_s = time.perf_counter() - t0
    applied = int(last.get("interaction_count", 0)) - int(before.get("interaction_count", 0))
    row = {
        "n_events": N,
        "publish_s": round(publish_s, 4),
        "total_s": round(total_s, 4),
        "applied": applied,
        "events_per_sec": round(N / publish_s, 2) if publish_s else None,
        "consume_events_per_sec": round(applied / total_s, 2) if total_s else None,
        "p50_s": None,
        "p95_s": None,
        "note": "Freshness histogram lives on the consumer Prometheus endpoint.",
    }
    print(row)
    path = ROOT / "reports" / "benchmark_results.json"
    blob = {}
    if path.exists():
        blob = json.loads(path.read_text(encoding="utf-8"))
    blob["stream"] = row
    blob["measured_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
