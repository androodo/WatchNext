#!/usr/bin/env python
"""Replay train history into Redis so serving has online features for known users."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json

import polars as pl
from redis import Redis

from pulserank_ml.common.schema import new_event
from pulserank_ml.online.processor import FeatureProcessor

PROCESSED = ROOT / "data" / "processed"


def main() -> None:
    n_users = int(os.environ.get("SEED_USERS", "50"))
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    train = pl.read_parquet(PROCESSED / "train.parquet")
    cats = json.loads((PROCESSED / "item_categories.json").read_text(encoding="utf-8"))
    r = Redis.from_url(redis_url, decode_responses=True)
    proc = FeatureProcessor(r, cats)

    users = [str(u) for u in train["user_id"].unique().sort().to_list()[:n_users]]
    subset = train.filter(pl.col("user_id").is_in(users)).sort("timestamp")
    applied = 0
    for row in subset.iter_rows(named=True):
        ev = new_event(
            user_id=str(row["user_id"]),
            item_id=str(row["item_id"]),
            event_type=row["event_type"],
            timestamp=datetime.fromtimestamp(int(row["timestamp"]), tz=UTC),
            value=float(row["value"]),
            event_id=f"seed-{row['user_id']}-{row['item_id']}-{row['timestamp']}",
        )
        proc.process_event(ev)
        applied += 1
    pop = pl.read_parquet(ROOT / "artifacts" / "popularity.parquet").head(200)
    r.set(
        "fallback:popularity",
        json.dumps([str(x) for x in pop["item_id"].to_list()]),
    )
    print(f"seeded {len(users)} users, {applied} events")


if __name__ == "__main__":
    main()
