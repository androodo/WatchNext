"""Random and popularity baselines."""

from __future__ import annotations

import random
from collections.abc import Sequence

import polars as pl

from watchnext.common.constants import POSITIVE_EVENT_TYPES


def popularity_ranking(train: pl.DataFrame, k: int | None = None) -> list[str]:
    """Items ranked by number of positive interactions in train."""
    pos = train.filter(pl.col("event_type").is_in(list(POSITIVE_EVENT_TYPES)))
    if pos.is_empty():
        pos = train
    ranked = pos.group_by("item_id").len().sort("len", descending=True).get_column("item_id").to_list()
    if k is not None:
        return [str(x) for x in ranked[:k]]
    return [str(x) for x in ranked]


def random_ranking(item_ids: Sequence[str], k: int, rng: random.Random | None = None) -> list[str]:
    rng = rng or random.Random(0)
    items = list(item_ids)
    rng.shuffle(items)
    return [str(x) for x in items[:k]]
