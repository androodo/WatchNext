from __future__ import annotations

import polars as pl
import pytest

from pulserank_ml.datasets.split import (
    TemporalLeakageError,
    temporal_split,
    validate_temporal_split,
)


def _df(ts: list[int]) -> pl.DataFrame:
    n = len(ts)
    return pl.DataFrame(
        {
            "user_id": [str(i % 3) for i in range(n)],
            "item_id": [str(i) for i in range(n)],
            "event_type": ["like"] * n,
            "timestamp": ts,
            "value": [1.0] * n,
        }
    )


def test_temporal_split_is_strictly_ordered():
    df = _df(list(range(100)))
    train, val, test = temporal_split(df)
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max() < test["timestamp"].min()
    assert train.height + val.height + test.height == 100


def test_detects_time_leakage():
    train = _df([10, 20])
    val = _df([5, 30])
    test = _df([40])
    with pytest.raises(TemporalLeakageError):
        validate_temporal_split(train, val, test)


def test_shuffled_source_still_splits_by_time():
    df = _df([9, 1, 5, 3, 8, 2, 7, 4, 6, 0, 10, 11])
    shuffled = df.sample(fraction=1.0, shuffle=True, seed=1)
    train, val, test = temporal_split(shuffled)
    assert train["timestamp"].max() < val["timestamp"].min()
    assert val["timestamp"].max() < test["timestamp"].min()
