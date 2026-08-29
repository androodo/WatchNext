from __future__ import annotations

from pulserank_ml.evaluation.metrics import (
    catalog_coverage,
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_perfect_ranking_metrics():
    rec = ["a", "b", "c"]
    rel = ["a", "b"]
    assert precision_at_k(rec, rel, 2) == 1.0
    assert recall_at_k(rec, rel, 2) == 1.0
    assert hit_rate_at_k(rec, rel, 2) == 1.0
    assert mrr(rec, rel) == 1.0
    assert ndcg_at_k(rec, rel, 2) == 1.0


def test_misses_are_zero():
    rec = ["x", "y"]
    rel = ["a"]
    assert precision_at_k(rec, rel, 2) == 0.0
    assert recall_at_k(rec, rel, 2) == 0.0
    assert hit_rate_at_k(rec, rel, 2) == 0.0
    assert mrr(rec, rel) == 0.0


def test_coverage():
    recs = [["a", "b"], ["b", "c"]]
    assert catalog_coverage(recs, catalog_size=4, k=2) == 0.75
