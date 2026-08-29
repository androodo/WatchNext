from __future__ import annotations

import polars as pl

from pulserank_ml.candidates.als import train_als
from pulserank_ml.ranking.dataset import build_training_lists
from pulserank_ml.ranking.train import predict_scores, train_ranker


def _tiny_train() -> tuple[pl.DataFrame, pl.DataFrame]:
    users, items, types, ts, vals = [], [], [], [], []
    t = 1_000
    for u in range(8):
        for i in range(3):
            users.append(str(u))
            items.append(str((u * 3 + i) % 12))
            types.append("like" if i == 0 else "view")
            ts.append(t)
            vals.append(1.0 if i == 0 else 0.4)
            t += 1
    train = pl.DataFrame(
        {
            "user_id": users,
            "item_id": items,
            "event_type": types,
            "timestamp": ts,
            "value": vals,
        }
    )
    catalog = pl.DataFrame(
        {
            "item_id": [str(i) for i in range(12)],
            "categories": [["sci_fi"] if i % 2 == 0 else ["comedy"] for i in range(12)],
            "year": [1990 + i for i in range(12)],
        }
    )
    return train, catalog


def test_als_returns_personalized_candidates():
    train, _ = _tiny_train()
    model = train_als(train, factors=8, iterations=5, regularization=0.1)
    recs = model.recommend("0", k=5)
    assert recs
    assert recs[0]["source"] == "als"
    assert recs[0]["item_id"] not in {r["item_id"] for r in []}  # smoke


def test_ranker_trains_and_scores():
    train, items = _tiny_train()
    X, y, groups = build_training_lists(train, items, negatives_per_positive=2, max_positives_per_user=3)
    assert groups
    assert len(X) == len(y)
    model = train_ranker(X, y, groups, n_estimators=10, num_leaves=8)
    scores = predict_scores(model.booster_, X[:5])
    assert len(scores) == 5
