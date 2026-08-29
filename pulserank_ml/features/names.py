"""Ranker feature names. Offline training and online ML service share this list."""

from __future__ import annotations

RANKER_FEATURES: list[str] = [
    "retrieval_score",
    "source_rank",
    "source_is_als",
    "source_is_popularity",
    "user_interaction_count",
    "user_views_24h",
    "user_likes_24h",
    "user_skips_24h",
    "user_watches_24h",
    "user_activity_7d",
    "user_avg_engagement",
    "item_popularity",
    "item_avg_rating",
    "item_rating_count",
    "item_like_rate",
    "user_item_affinity",
    "genre_match_count",
    "previously_interacted",
    "hour_of_day",
    "day_of_week",
    "item_year_norm",
]


def feature_vector(values: dict[str, float]) -> list[float]:
    return [float(values.get(name, 0.0)) for name in RANKER_FEATURES]
