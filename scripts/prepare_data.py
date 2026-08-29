#!/usr/bin/env python
"""Convert MovieLens into canonical tables and apply a temporal split."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from watchnext.datasets.movielens import load_raw_movielens, to_canonical
from watchnext.datasets.split import temporal_split

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    movies, ratings, users = load_raw_movielens(RAW)
    users_df, items, interactions = to_canonical(movies, ratings, users)
    train, val, test = temporal_split(interactions)

    users_df.write_parquet(PROCESSED / "users.parquet")
    items.write_parquet(PROCESSED / "items.parquet")
    interactions.write_parquet(PROCESSED / "interactions.parquet")
    train.write_parquet(PROCESSED / "train.parquet")
    val.write_parquet(PROCESSED / "val.parquet")
    test.write_parquet(PROCESSED / "test.parquet")

    # Compact item category map for the feature consumer.
    cat_map = {str(r["item_id"]): list(r["categories"]) for r in items.iter_rows(named=True)}
    import orjson

    (PROCESSED / "item_categories.json").write_bytes(orjson.dumps(cat_map))

    print("users", users_df.height)
    print("items", items.height)
    print("interactions", interactions.height)
    print("train", train.height, "ts", int(train["timestamp"].min()), int(train["timestamp"].max()))
    print("val", val.height, "ts", int(val["timestamp"].min()), int(val["timestamp"].max()))
    print("test", test.height, "ts", int(test["timestamp"].min()), int(test["timestamp"].max()))
    print("wrote", PROCESSED)


if __name__ == "__main__":
    main()
