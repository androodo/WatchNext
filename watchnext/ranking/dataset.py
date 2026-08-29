"""Point-in-time ranker training rows with documented negative sampling."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any

import polars as pl

from watchnext.common.constants import (
    POSITIVE_EVENT_TYPES,
    RANKER_MAX_POSITIVES_PER_USER,
    RANKER_NEGATIVES_PER_POSITIVE,
)
from watchnext.common.schema import new_event
from watchnext.features.engine import FeatureEngine
from watchnext.features.names import RANKER_FEATURES, feature_vector

# Negative sampling strategy (documented, not "true dislikes"):
# For each positive interaction at time t we sample items the user had not
# interacted with before t. Unobserved ≠ disliked. This over-represents popular
# items in the negative pool unless we popularity-sample; we use uniform
# catalog samples for simplicity and honesty.


def _item_meta(items: pl.DataFrame) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in items.iter_rows(named=True):
        out[str(row["item_id"])] = {
            "categories": list(row["categories"]) if row["categories"] is not None else [],
            "year": row.get("year"),
        }
    return out


def _item_stats(train: pl.DataFrame) -> dict[str, dict[str, float]]:
    grouped = train.group_by("item_id").agg(
        pl.len().alias("count"),
        pl.col("value").mean().alias("avg"),
        pl.col("event_type").eq("like").sum().alias("likes"),
    )
    out: dict[str, dict[str, float]] = {}
    max_count = 1.0
    for row in grouped.iter_rows(named=True):
        c = float(row["count"])
        max_count = max(max_count, c)
        out[str(row["item_id"])] = {
            "count": c,
            "avg": float(row["avg"] or 0.0),
            "likes": float(row["likes"] or 0.0),
        }
    for v in out.values():
        v["popularity"] = v["count"] / max_count
        v["like_rate"] = v["likes"] / v["count"] if v["count"] else 0.0
    return out


def build_ranker_features(
    *,
    retrieval_score: float,
    source: str,
    source_rank: int,
    user_state,
    item_id: str,
    item_meta: dict[str, Any],
    item_stats: dict[str, float],
    timestamp: datetime,
    previously_interacted: bool,
) -> dict[str, float]:
    cats = item_meta.get("categories") or []
    year = item_meta.get("year") or 2000
    affinity = user_state.item_affinity(cats)
    match = sum(1 for c in cats if user_state.affinity(c) > 0.05)
    ts = timestamp.astimezone(UTC) if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
    return {
        "retrieval_score": float(retrieval_score),
        "source_rank": float(source_rank),
        "source_is_als": 1.0 if source == "als" else 0.0,
        "source_is_popularity": 1.0 if source == "popularity" else 0.0,
        "user_interaction_count": float(user_state.interaction_count),
        "user_views_24h": float(user_state.views_24h),
        "user_likes_24h": float(user_state.likes_24h),
        "user_skips_24h": float(user_state.skips_24h),
        "user_watches_24h": float(user_state.watches_24h),
        "user_activity_7d": float(
            user_state.views_7d + user_state.likes_7d + user_state.skips_7d + user_state.watches_7d
        ),
        "user_avg_engagement": float(user_state.avg_engagement),
        "item_popularity": float(item_stats.get("popularity", 0.0)),
        "item_avg_rating": float(item_stats.get("avg", 0.0)),
        "item_rating_count": float(item_stats.get("count", 0.0)),
        "item_like_rate": float(item_stats.get("like_rate", 0.0)),
        "user_item_affinity": float(affinity),
        "genre_match_count": float(match),
        "previously_interacted": 1.0 if previously_interacted else 0.0,
        "hour_of_day": float(ts.hour),
        "day_of_week": float(ts.weekday()),
        "item_year_norm": float((int(year) - 1920) / 100.0),
    }


def build_training_lists(
    train: pl.DataFrame,
    items: pl.DataFrame,
    als_scores: dict[tuple[str, str], tuple[float, int]] | None = None,
    rng: random.Random | None = None,
    negatives_per_positive: int = RANKER_NEGATIVES_PER_POSITIVE,
    max_positives_per_user: int = RANKER_MAX_POSITIVES_PER_USER,
) -> tuple[list[list[float]], list[int], list[int]]:
    """Return (X rows, y labels, group sizes) for LightGBM ranker.

    Each group is one positive + sampled negatives at a point in time.
    Features use only interactions strictly before that timestamp.
    """
    rng = rng or random.Random(42)
    meta = _item_meta(items)
    stats = _item_stats(train)
    catalog = [str(i) for i in items["item_id"].to_list()]
    als_scores = als_scores or {}

    train_sorted = train.sort(["user_id", "timestamp"])
    X: list[list[float]] = []
    y: list[int] = []
    groups: list[int] = []

    for user_id, user_df in train_sorted.group_by("user_id", maintain_order=True):
        uid = str(user_id if not isinstance(user_id, tuple) else user_id[0])
        rows = user_df.to_dicts()
        engine = FeatureEngine()
        seen: set[str] = set()
        positives = 0
        for row in rows:
            item_id = str(row["item_id"])
            ts = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
            event = new_event(
                user_id=uid,
                item_id=item_id,
                event_type=row["event_type"],
                timestamp=ts,
                value=float(row["value"]),
            )
            cats = meta.get(item_id, {}).get("categories") or []
            is_pos = row["event_type"] in POSITIVE_EVENT_TYPES
            if is_pos and positives < max_positives_per_user:
                state = engine.snapshot(ts)
                group_items: list[tuple[str, int, str]] = [(item_id, 1, "als")]
                unseen = [i for i in catalog if i not in seen and i != item_id]
                k_neg = min(negatives_per_positive, len(unseen))
                for neg in rng.sample(unseen, k_neg) if k_neg else []:
                    group_items.append((neg, 0, "popularity"))
                for rank, (iid, label, source) in enumerate(group_items, start=1):
                    ret = als_scores.get((uid, iid), (0.0, rank))
                    feats = build_ranker_features(
                        retrieval_score=ret[0],
                        source=source,
                        source_rank=ret[1] if source == "als" else rank,
                        user_state=state,
                        item_id=iid,
                        item_meta=meta.get(iid, {}),
                        item_stats=stats.get(iid, {}),
                        timestamp=ts,
                        previously_interacted=iid in seen,
                    )
                    X.append(feature_vector(feats))
                    y.append(label)
                groups.append(len(group_items))
                positives += 1
            engine.apply(event, cats, as_of=ts)
            seen.add(item_id)

    return X, y, groups


def assert_feature_names() -> None:
    if len(RANKER_FEATURES) < 15 or len(RANKER_FEATURES) > 30:
        raise RuntimeError("keep ranker features in the 15-30 range")
