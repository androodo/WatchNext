#!/usr/bin/env python
"""Evaluate random, popularity, ALS, and ALS+ranker. Writes reports/ from real metrics."""

from __future__ import annotations

import random
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl

from pulserank_ml.candidates.als import load_als
from pulserank_ml.candidates.popularity import (
    compute_popularity,
    load_popularity,
    popularity_candidates,
)
from pulserank_ml.candidates.retrieve import retrieve_for_user
from pulserank_ml.common.constants import POSITIVE_EVENT_TYPES
from pulserank_ml.evaluation.baselines import popularity_ranking, random_ranking
from pulserank_ml.evaluation.metrics import (
    catalog_coverage,
    hit_rate_at_k,
    mean_metric,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from pulserank_ml.evaluation.report import write_evaluation_report
from pulserank_ml.features.engine import FeatureEngine
from pulserank_ml.features.names import feature_vector
from pulserank_ml.ranking.dataset import build_ranker_features
from pulserank_ml.ranking.train import load_ranker, predict_scores

PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"


def _relevant_by_user(df: pl.DataFrame) -> dict[str, set[str]]:
    pos = df.filter(pl.col("event_type").is_in(list(POSITIVE_EVENT_TYPES)))
    out: dict[str, set[str]] = defaultdict(set)
    for row in pos.select("user_id", "item_id").iter_rows(named=True):
        out[str(row["user_id"])].add(str(row["item_id"]))
    return dict(out)


def _ranking_metrics(recs: dict[str, list[str]], relevant: dict[str, set[str]], catalog: int) -> dict:
    k = 10
    return {
        "precision@10": mean_metric(recs, relevant, precision_at_k, k),
        "recall@10": mean_metric(recs, relevant, recall_at_k, k),
        "ndcg@10": mean_metric(recs, relevant, ndcg_at_k, k),
        "mrr": mean_metric(recs, relevant, mrr),
        "hit_rate@10": mean_metric(recs, relevant, hit_rate_at_k, k),
        "coverage@10": catalog_coverage(list(recs.values()), catalog, k),
    }


def _candidate_metrics(cands: dict[str, list[str]], relevant: dict[str, set[str]]) -> dict:
    return {
        "recall@50": mean_metric(cands, relevant, recall_at_k, 50),
        "recall@100": mean_metric(cands, relevant, recall_at_k, 100),
        "hit_rate@50": mean_metric(cands, relevant, hit_rate_at_k, 50),
        "hit_rate@100": mean_metric(cands, relevant, hit_rate_at_k, 100),
    }


def main() -> None:
    train = pl.read_parquet(PROCESSED / "train.parquet")
    test = pl.read_parquet(PROCESSED / "test.parquet")
    val = pl.read_parquet(PROCESSED / "val.parquet")
    items = pl.read_parquet(PROCESSED / "items.parquet")
    catalog = [str(i) for i in items["item_id"].to_list()]
    relevant = _relevant_by_user(test)
    train_users = set(str(u) for u in train["user_id"].unique().to_list())
    eval_users = [u for u in relevant if u in train_users]
    # Cap evaluation users so the script finishes on a laptop.
    eval_users = sorted(eval_users)[:400]
    relevant = {u: relevant[u] for u in eval_users}

    rng = random.Random(0)
    pop_list = popularity_ranking(train)
    pop_recs = {u: [i for i in pop_list if True][:10] for u in eval_users}
    rand_recs = {u: random_ranking(catalog, 10, random.Random(rng.randint(0, 10_000))) for u in eval_users}

    als = load_als(ARTIFACTS / "als.npz")
    pop_df = load_popularity(ARTIFACTS / "popularity.parquet")
    booster = load_ranker(ARTIFACTS / "ranker-v1.txt")

    als_feed: dict[str, list[str]] = {}
    als_cands: dict[str, list[str]] = {}
    pop_cands: dict[str, list[str]] = {}
    ranked_feed: dict[str, list[str]] = {}

    item_meta = {
        str(r["item_id"]): {"categories": list(r["categories"] or []), "year": r.get("year")}
        for r in items.iter_rows(named=True)
    }
    stats_df = compute_popularity(train)
    item_stats = {
        str(r["item_id"]): {
            "popularity": float(r["positive_count"]) / float(stats_df["positive_count"].max() or 1),
            "avg": float(r["avg_rating"] or 0),
            "count": float(r["interaction_count"] or 0),
            "like_rate": float(r["like_rate"] or 0),
        }
        for r in stats_df.iter_rows(named=True)
    }

    # Point-in-time user state at end of train (no test leakage).
    train_by_user = train.filter(pl.col("user_id").is_in(eval_users)).sort("timestamp")
    engines: dict[str, FeatureEngine] = {u: FeatureEngine() for u in eval_users}
    cutoff = datetime.fromtimestamp(int(train["timestamp"].max()), tz=UTC)
    for row in train_by_user.iter_rows(named=True):
        uid = str(row["user_id"])
        iid = str(row["item_id"])
        from pulserank_ml.common.schema import new_event

        ev = new_event(
            user_id=uid,
            item_id=iid,
            event_type=row["event_type"],
            timestamp=datetime.fromtimestamp(int(row["timestamp"]), tz=UTC),
            value=float(row["value"]),
        )
        engines[uid].apply(ev, item_meta.get(iid, {}).get("categories") or [], as_of=ev.timestamp)

    for u in eval_users:
        exclude = set()
        als_list = retrieve_for_user(u, als, pop_df, k=100, exclude=exclude)
        pop_list_c = popularity_candidates(pop_df, k=100, exclude=exclude)
        als_cands[u] = [c["item_id"] for c in als_list]
        pop_cands[u] = [c["item_id"] for c in pop_list_c]
        als_feed[u] = als_cands[u][:10]

        state = engines[u].snapshot(cutoff)
        X = []
        for c in als_list:
            feats = build_ranker_features(
                retrieval_score=c["retrieval_score"],
                source=c["source"],
                source_rank=c["source_rank"],
                user_state=state,
                item_id=c["item_id"],
                item_meta=item_meta.get(c["item_id"], {}),
                item_stats=item_stats.get(c["item_id"], {}),
                timestamp=cutoff,
                previously_interacted=c["item_id"] in state.interacted_items,
            )
            X.append(feature_vector(feats))
        scores = predict_scores(booster, X)
        order = sorted(range(len(als_list)), key=lambda i: scores[i], reverse=True)
        ranked_feed[u] = [als_list[i]["item_id"] for i in order[:10]]

    results = {
        "dataset": "MovieLens 1M",
        "n_train": train.height,
        "n_val": val.height,
        "n_test": test.height,
        "n_eval_users": len(eval_users),
        "catalog_size": len(catalog),
        "candidates": {
            "popularity": _candidate_metrics(pop_cands, relevant),
            "als": _candidate_metrics(als_cands, relevant),
        },
        "ranking": {
            "random": _ranking_metrics(rand_recs, relevant, len(catalog)),
            "popularity": _ranking_metrics(pop_recs, relevant, len(catalog)),
            "als": _ranking_metrics(als_feed, relevant, len(catalog)),
            "als+ranker": _ranking_metrics(ranked_feed, relevant, len(catalog)),
        },
    }
    write_evaluation_report(results, REPORTS / "offline_evaluation.json", REPORTS / "offline_evaluation.md")
    print(json_dumps(results))


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, indent=2)


if __name__ == "__main__":
    main()
