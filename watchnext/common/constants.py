"""Shared constants. One source of truth for event types and feature formulas."""

from __future__ import annotations

SCHEMA_VERSION = 1

EVENT_TYPES = (
    "impression",
    "view",
    "like",
    "skip",
    "watch",
    "dislike",
    "rating",
)

# Signed engagement used by affinity EMA and avg_engagement.
# Impressions do not change affinity.
EVENT_WEIGHTS: dict[str, float] = {
    "impression": 0.0,
    "view": 0.4,
    "like": 1.0,
    "watch": 0.8,
    "skip": -0.3,
    "dislike": -1.0,
}

# EMA step for category affinity. Same value offline and online.
AFFINITY_ALPHA = 0.15

# Cap recent history used for 24h / 7d recounts.
HISTORY_CAP = 500

WINDOW_24H_SECONDS = 24 * 60 * 60
WINDOW_7D_SECONDS = 7 * 24 * 60 * 60

DEDUPE_TTL_SECONDS = 7 * 24 * 60 * 60

POSITIVE_EVENT_TYPES = frozenset({"like", "watch"})
NEGATIVE_EVENT_TYPES = frozenset({"skip", "dislike"})

CANDIDATE_K = 100
DEFAULT_FEED_K = 36
MAX_FEED_K = 80
MAX_CANDIDATE_K = 250

TEMPORAL_TRAIN_FRACTION = 0.80
TEMPORAL_VAL_FRACTION = 0.10
# remainder is test (0.10)

RANKER_NEGATIVES_PER_POSITIVE = 4
RANKER_MAX_POSITIVES_PER_USER = 40
