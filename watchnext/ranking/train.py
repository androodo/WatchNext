"""LightGBM ranker train / load / predict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import orjson

from watchnext.features.names import RANKER_FEATURES


def train_ranker(
    X: list[list[float]],
    y: list[int],
    groups: list[int],
    *,
    num_leaves: int = 31,
    learning_rate: float = 0.05,
    n_estimators: int = 80,
    random_state: int = 42,
) -> lgb.LGBMRanker:
    model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        num_leaves=num_leaves,
        learning_rate=learning_rate,
        n_estimators=n_estimators,
        random_state=random_state,
        verbosity=-1,
    )
    model.fit(np.asarray(X, dtype=np.float32), np.asarray(y), group=groups)
    return model


def save_ranker(model: lgb.LGBMRanker, path: Path, extra: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(path))
    meta = {
        "feature_names": RANKER_FEATURES,
        "model_version": path.stem,
        **(extra or {}),
    }
    path.with_suffix(".json").write_bytes(orjson.dumps(meta, option=orjson.OPT_INDENT_2))


def load_ranker(path: Path) -> lgb.Booster:
    return lgb.Booster(model_file=str(path))


def predict_scores(booster: lgb.Booster, X: list[list[float]]) -> list[float]:
    if not X:
        return []
    preds = booster.predict(np.asarray(X, dtype=np.float32))
    return [float(x) for x in preds]
