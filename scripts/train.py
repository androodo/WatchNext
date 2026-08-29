#!/usr/bin/env python
"""Train popularity + ALS candidate models and the LightGBM ranker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl

from watchnext.candidates.als import save_als, train_als
from watchnext.candidates.popularity import compute_popularity, save_popularity
from watchnext.ranking.dataset import build_training_lists
from watchnext.ranking.train import save_ranker, train_ranker

PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"


def main() -> None:
    train = pl.read_parquet(PROCESSED / "train.parquet")
    items = pl.read_parquet(PROCESSED / "items.parquet")

    print("computing popularity")
    pop = compute_popularity(train)
    save_popularity(pop, ARTIFACTS / "popularity.parquet")

    print("training ALS")
    als = train_als(train, factors=64, iterations=12)
    save_als(als, ARTIFACTS / "als.npz")

    print("building ranker dataset (point-in-time features + sampled negatives)")
    # Limit users for ranker construction time on laptops; full train is still
    # used for ALS. Documented in docs/RECOMMENDATION_SYSTEM.md.
    unique_users = train["user_id"].unique().to_list()
    ranker_users = set(str(u) for u in unique_users[:800])
    ranker_train = train.filter(pl.col("user_id").is_in(list(ranker_users)))
    X, y, groups = build_training_lists(ranker_train, items)
    print(f"ranker rows={len(X)} groups={len(groups)}")
    model = train_ranker(X, y, groups)
    save_ranker(
        model,
        ARTIFACTS / "ranker-v1.txt",
        extra={
            "n_rows": len(X),
            "n_groups": len(groups),
            "n_users_sampled": len(ranker_users),
        },
    )
    (ARTIFACTS / "training_summary.json").write_text(
        json.dumps(
            {
                "als_users": len(als.user_map),
                "als_items": len(als.item_map),
                "ranker_rows": len(X),
                "ranker_groups": len(groups),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("wrote", ARTIFACTS)


if __name__ == "__main__":
    main()
