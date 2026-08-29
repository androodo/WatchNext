"""Temporal splits. Never shuffle interactions across train/val/test."""

from __future__ import annotations

import polars as pl

from watchnext.common.constants import TEMPORAL_TRAIN_FRACTION, TEMPORAL_VAL_FRACTION


class TemporalLeakageError(AssertionError):
    pass


def temporal_split(
    interactions: pl.DataFrame,
    train_frac: float = TEMPORAL_TRAIN_FRACTION,
    val_frac: float = TEMPORAL_VAL_FRACTION,
    timestamp_col: str = "timestamp",
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Split by global timestamp quantiles: earliest train_frac, next val_frac, rest test.

    Guarantees max(train.ts) < min(val.ts) and max(val.ts) < min(test.ts) after
    assigning ties on the cut timestamps to the later split.
    """
    if timestamp_col not in interactions.columns:
        raise ValueError(f"missing {timestamp_col}")
    if interactions.is_empty():
        raise ValueError("no interactions to split")

    sorted_df = interactions.sort(timestamp_col)
    ts = sorted_df[timestamp_col]
    t_train_end = ts.quantile(train_frac)
    t_val_end = ts.quantile(train_frac + val_frac)
    if t_train_end is None or t_val_end is None:
        raise ValueError("could not compute timestamp quantiles")

    train = sorted_df.filter(pl.col(timestamp_col) < t_train_end)
    val = sorted_df.filter((pl.col(timestamp_col) >= t_train_end) & (pl.col(timestamp_col) < t_val_end))
    test = sorted_df.filter(pl.col(timestamp_col) >= t_val_end)

    validate_temporal_split(train, val, test, timestamp_col=timestamp_col)
    return train, val, test


def validate_temporal_split(
    train: pl.DataFrame,
    val: pl.DataFrame,
    test: pl.DataFrame,
    timestamp_col: str = "timestamp",
) -> None:
    """Fail the build if any later split leaks into an earlier one."""
    if train.is_empty() or val.is_empty() or test.is_empty():
        raise TemporalLeakageError("split produced an empty partition")

    train_max = train[timestamp_col].max()
    val_min = val[timestamp_col].min()
    val_max = val[timestamp_col].max()
    test_min = test[timestamp_col].min()

    if not (train_max < val_min):
        raise TemporalLeakageError(f"train max ts {train_max} is not strictly before val min ts {val_min}")
    if not (val_max < test_min):
        raise TemporalLeakageError(f"val max ts {val_max} is not strictly before test min ts {test_min}")

    # Extra guard: no identical (user, item, timestamp) row in two splits.
    keys = ["user_id", "item_id", timestamp_col]
    for a, b, name in (
        (train, val, "train/val"),
        (val, test, "val/test"),
        (train, test, "train/test"),
    ):
        overlap = a.select(keys).join(b.select(keys), on=keys, how="inner")
        if overlap.height > 0:
            raise TemporalLeakageError(f"duplicate interactions across {name}")
