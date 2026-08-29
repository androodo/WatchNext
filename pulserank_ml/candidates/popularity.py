"""Popularity candidate source."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
import polars as pl

from pulserank_ml.common.constants import CANDIDATE_K, POSITIVE_EVENT_TYPES


def compute_popularity(train: pl.DataFrame) -> pl.DataFrame:
    pos = train.filter(pl.col("event_type").is_in(list(POSITIVE_EVENT_TYPES)))
    if pos.is_empty():
        pos = train
    stats = (
        train.group_by("item_id")
        .agg(
            pl.len().alias("interaction_count"),
            pl.col("value").mean().alias("avg_engagement"),
            pl.col("rating").mean().alias("avg_rating")
            if "rating" in train.columns
            else pl.col("value").mean().alias("avg_rating"),
        )
        .join(
            pos.group_by("item_id").len().rename({"len": "positive_count"}),
            on="item_id",
            how="left",
        )
        .with_columns(pl.col("positive_count").fill_null(0))
        .sort(["positive_count", "interaction_count"], descending=True)
    )
    stats = stats.with_columns(
        (pl.col("positive_count") / pl.col("interaction_count").clip(lower_bound=1)).alias("like_rate")
    )
    return stats


def popularity_candidates(
    popularity: pl.DataFrame,
    k: int = CANDIDATE_K,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    exclude = exclude or set()
    out: list[dict[str, Any]] = []
    max_count = float(popularity["positive_count"].max() or 1)
    rank = 0
    for row in popularity.iter_rows(named=True):
        item_id = str(row["item_id"])
        if item_id in exclude:
            continue
        rank += 1
        score = float(row["positive_count"]) / max_count if max_count else 0.0
        out.append(
            {
                "item_id": item_id,
                "source": "popularity",
                "retrieval_score": round(score, 6),
                "source_rank": rank,
            }
        )
        if len(out) >= k:
            break
    return out


def save_popularity(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def load_popularity(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


def popularity_json(df: pl.DataFrame, k: int = 500) -> bytes:
    rows = df.head(k).select("item_id", "positive_count", "avg_rating", "like_rate").to_dicts()
    return orjson.dumps(rows)
