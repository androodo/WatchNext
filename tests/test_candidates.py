from __future__ import annotations

import polars as pl

from pulserank_ml.candidates.popularity import compute_popularity, popularity_candidates
from pulserank_ml.candidates.retrieve import merge_candidates
from pulserank_ml.evaluation.baselines import popularity_ranking, random_ranking


def test_popularity_orders_by_positives():
    train = pl.DataFrame(
        {
            "user_id": ["1", "2", "3", "1"],
            "item_id": ["hot", "hot", "cold", "hot"],
            "event_type": ["like", "like", "view", "watch"],
            "value": [1.0, 1.0, 0.4, 0.8],
        }
    )
    ranked = popularity_ranking(train)
    assert ranked[0] == "hot"
    pop = compute_popularity(train)
    cands = popularity_candidates(pop, k=10)
    assert cands[0]["item_id"] == "hot"
    assert cands[0]["source"] == "popularity"


def test_random_is_deterministic_with_seed():
    items = [str(i) for i in range(20)]
    a = random_ranking(items, 5, rng=__import__("random").Random(0))
    b = random_ranking(items, 5, rng=__import__("random").Random(0))
    assert a == b


def test_merge_prefers_als_then_fills():
    als = [{"item_id": "1", "source": "als", "retrieval_score": 0.9, "source_rank": 1}]
    pop = [
        {"item_id": "1", "source": "popularity", "retrieval_score": 1.0, "source_rank": 1},
        {"item_id": "2", "source": "popularity", "retrieval_score": 0.5, "source_rank": 2},
    ]
    merged = merge_candidates(als, pop, k=10)
    assert [c["item_id"] for c in merged] == ["1", "2"]
    assert merged[0]["source"] == "als"
