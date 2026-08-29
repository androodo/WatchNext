"""Ranking / retrieval metrics. Computed from actual predictions, never hardcoded."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import numpy as np


def _as_set(items: Iterable[str]) -> set[str]:
    return {str(x) for x in items}


def precision_at_k(recommended: Sequence[str], relevant: Iterable[str], k: int) -> float:
    rec = list(recommended)[:k]
    if not rec:
        return 0.0
    rel = _as_set(relevant)
    hits = sum(1 for x in rec if x in rel)
    return hits / len(rec)


def recall_at_k(recommended: Sequence[str], relevant: Iterable[str], k: int) -> float:
    rel = _as_set(relevant)
    if not rel:
        return 0.0
    rec = list(recommended)[:k]
    hits = sum(1 for x in rec if x in rel)
    return hits / len(rel)


def hit_rate_at_k(recommended: Sequence[str], relevant: Iterable[str], k: int) -> float:
    rel = _as_set(relevant)
    if not rel:
        return 0.0
    rec = set(list(recommended)[:k])
    return 1.0 if rec & rel else 0.0


def mrr(recommended: Sequence[str], relevant: Iterable[str]) -> float:
    rel = _as_set(relevant)
    for i, item in enumerate(recommended, start=1):
        if item in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(recommended: Sequence[str], relevant: Iterable[str], k: int) -> float:
    rel = _as_set(relevant)
    rec = list(recommended)[:k]
    dcg = 0.0
    for i, item in enumerate(rec, start=1):
        if item in rel:
            dcg += 1.0 / np.log2(i + 1)
    ideal_hits = min(len(rel), k)
    idcg = sum(1.0 / np.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def catalog_coverage(all_recommended: Sequence[Sequence[str]], catalog_size: int, k: int) -> float:
    if catalog_size <= 0:
        return 0.0
    seen: set[str] = set()
    for rec in all_recommended:
        seen.update(str(x) for x in list(rec)[:k])
    return len(seen) / catalog_size


def mean_metric(
    recs_by_user: Mapping[str, Sequence[str]],
    relevant_by_user: Mapping[str, Iterable[str]],
    metric_fn,
    k: int | None = None,
) -> float:
    scores = []
    for user, rec in recs_by_user.items():
        rel = list(relevant_by_user.get(user, []))
        if not rel:
            continue
        if k is None:
            scores.append(float(metric_fn(rec, rel)))
        else:
            scores.append(float(metric_fn(rec, rel, k)))
    if not scores:
        return 0.0
    return float(np.mean(scores))
