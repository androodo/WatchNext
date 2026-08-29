"""Merge candidate sources for a user."""

from __future__ import annotations

from typing import Any

from pulserank_ml.candidates.als import ALSModel
from pulserank_ml.candidates.popularity import popularity_candidates
from pulserank_ml.common.constants import CANDIDATE_K


def merge_candidates(
    als_cands: list[dict[str, Any]],
    pop_cands: list[dict[str, Any]],
    k: int = CANDIDATE_K,
) -> list[dict[str, Any]]:
    """ALS first, fill remaining slots with popularity. Dedupe by item_id."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for c in als_cands + pop_cands:
        iid = str(c["item_id"])
        if iid in seen:
            continue
        seen.add(iid)
        out.append(c)
        if len(out) >= k:
            break
    return out


def retrieve_for_user(
    user_id: str,
    als: ALSModel | None,
    popularity,
    k: int = CANDIDATE_K,
    exclude: set[str] | None = None,
    cold_start: bool = False,
) -> list[dict[str, Any]]:
    pop = popularity_candidates(popularity, k=k, exclude=exclude)
    if cold_start or als is None:
        return pop[:k]
    als_cands = als.recommend(user_id, k=k, exclude=exclude)
    if not als_cands:
        return pop[:k]
    return merge_candidates(als_cands, pop, k=k)
