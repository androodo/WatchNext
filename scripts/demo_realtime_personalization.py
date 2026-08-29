#!/usr/bin/env python
"""DEMO 3: like sci-fi / skip comedy, then show the feed moving.

Requires: docker compose stack up, Redis seeded, ML artifacts present.
Prints actual before/after affinities and category counts. Never hardcodes them.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "http://localhost:8080"


def http_json(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def category_counts(recs: list[dict], target: str) -> int:
    n = 0
    for item in recs:
        cats = [c.lower().replace("-", "_") for c in (item.get("categories") or [])]
        if target in cats:
            n += 1
    return n


def affinity(feats: dict, name: str) -> float:
    return float((feats.get("affinities") or {}).get(name, 0.0))


def pick_items(target: str, limit: int) -> list[str]:
    import polars as pl

    items = pl.read_parquet(ROOT / "data" / "processed" / "items.parquet")
    out = []
    for row in items.iter_rows(named=True):
        cats = [str(c).lower().replace("-", "_") for c in (row["categories"] or [])]
        if target in cats:
            out.append(str(row["item_id"]))
        if len(out) >= limit:
            break
    return out


def post_event(user_id: str, item_id: str, event_type: str) -> None:
    http_json(
        "POST",
        "/v1/events",
        {
            "event_id": str(uuid.uuid4()),
            "schema_version": 1,
            "user_id": str(user_id),
            "item_id": str(item_id),
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


def wait_for_affinity(user_id: str, name: str, before: float, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = http_json("GET", f"/v1/users/{user_id}/features")["features"]
        if affinity(last, name) != before:
            return last
        time.sleep(0.4)
    return last


def main() -> None:
    user_id = sys.argv[1] if len(sys.argv) > 1 else "1001"
    try:
        http_json("GET", "/health")
    except URLError as exc:
        raise SystemExit(f"API not reachable at {API}: {exc}") from exc

    before_feed = http_json("GET", f"/v1/recommendations/{user_id}?limit=10")
    before_feats = http_json("GET", f"/v1/users/{user_id}/features")["features"]
    sci_items = pick_items("sci_fi", 8)
    comedy_items = pick_items("comedy", 4)
    if not sci_items:
        raise SystemExit("no sci_fi items in processed catalog")

    print("BEFORE")
    print(f"  Comedy affinity: {affinity(before_feats, 'comedy'):.4f}")
    print(f"  Sci-Fi affinity: {affinity(before_feats, 'sci_fi'):.4f}")
    print(f"  Top-10 Sci-Fi items: {category_counts(before_feed['recommendations'], 'sci_fi')}")
    print(f"  experiment={before_feed.get('experiment')} model={before_feed.get('model_version')}")

    for iid in sci_items:
        post_event(user_id, iid, "like")
    for iid in comedy_items:
        post_event(user_id, iid, "skip")

    after_feats = wait_for_affinity(user_id, "sci_fi", affinity(before_feats, "sci_fi"))
    after_feed = http_json("GET", f"/v1/recommendations/{user_id}?limit=10")

    print("AFTER")
    print(f"  Comedy affinity: {affinity(after_feats, 'comedy'):.4f}")
    print(f"  Sci-Fi affinity: {affinity(after_feats, 'sci_fi'):.4f}")
    print(f"  Top-10 Sci-Fi items: {category_counts(after_feed['recommendations'], 'sci_fi')}")
    print(f"  experiment={after_feed.get('experiment')} model={after_feed.get('model_version')}")
    print(f"  fallback_used={after_feed.get('fallback_used')}")

    out = {
        "user_id": user_id,
        "before": {
            "comedy": affinity(before_feats, "comedy"),
            "sci_fi": affinity(before_feats, "sci_fi"),
            "sci_fi_in_top10": category_counts(before_feed["recommendations"], "sci_fi"),
        },
        "after": {
            "comedy": affinity(after_feats, "comedy"),
            "sci_fi": affinity(after_feats, "sci_fi"),
            "sci_fi_in_top10": category_counts(after_feed["recommendations"], "sci_fi"),
        },
    }
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "demo_realtime.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
