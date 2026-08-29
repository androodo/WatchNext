"""Load artifacts and serve candidates + ranking. Internal API only."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pulserank_ml.candidates.als import ALSModel, load_als
from pulserank_ml.candidates.popularity import load_popularity
from pulserank_ml.candidates.retrieve import retrieve_for_user
from pulserank_ml.common.constants import CANDIDATE_K
from pulserank_ml.features.engine import UserFeatureState
from pulserank_ml.features.names import feature_vector
from pulserank_ml.ranking.dataset import build_ranker_features
from pulserank_ml.ranking.train import load_ranker, predict_scores

log = structlog.get_logger("ml_service")

ROOT = Path(os.environ.get("PULSERANK_ROOT", Path(__file__).resolve().parents[2]))
ARTIFACTS = Path(os.environ.get("PULSERANK_ARTIFACTS", ROOT / "artifacts"))
PROCESSED = Path(os.environ.get("PULSERANK_PROCESSED", ROOT / "data" / "processed"))


class AppState:
    als: ALSModel | None = None
    popularity: Any = None
    ranker: Any = None
    items: dict[str, dict[str, Any]]
    item_stats: dict[str, dict[str, float]]
    model_version: str = "ranker-v1"
    ready: bool = False

    def __init__(self) -> None:
        self.items = {}
        self.item_stats = {}


STATE = AppState()


def _load() -> None:
    pop_path = ARTIFACTS / "popularity.parquet"
    items_path = PROCESSED / "items.parquet"
    if pop_path.exists():
        STATE.popularity = load_popularity(pop_path)
        max_pos = float(STATE.popularity["positive_count"].max() or 1)
        STATE.item_stats = {
            str(r["item_id"]): {
                "popularity": float(r["positive_count"]) / max_pos,
                "avg": float(r["avg_rating"] or 0.0),
                "count": float(r["interaction_count"] or 0.0),
                "like_rate": float(r["like_rate"] or 0.0),
            }
            for r in STATE.popularity.iter_rows(named=True)
        }
    if items_path.exists():
        items = pl.read_parquet(items_path)
        STATE.items = {
            str(r["item_id"]): {
                "title": r.get("title"),
                "categories": list(r["categories"] or []),
                "year": r.get("year"),
            }
            for r in items.iter_rows(named=True)
        }
    als_path = ARTIFACTS / "als.npz"
    if als_path.exists():
        STATE.als = load_als(als_path)
    ranker_path = ARTIFACTS / "ranker-v1.txt"
    if ranker_path.exists():
        STATE.ranker = load_ranker(ranker_path)
        STATE.model_version = "ranker-v1"
    STATE.ready = STATE.popularity is not None
    log.info(
        "ml_artifacts_loaded",
        als=STATE.als is not None,
        ranker=STATE.ranker is not None,
        items=len(STATE.items),
        ready=STATE.ready,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _load()
    yield


app = FastAPI(title="PulseRank ML Service", lifespan=lifespan)


class CandidateRequest(BaseModel):
    user_id: str
    request_id: str | None = None
    k: int = CANDIDATE_K
    exclude: list[str] = Field(default_factory=list)


class RankCandidate(BaseModel):
    item_id: str
    source: str = "als"
    retrieval_score: float = 0.0
    source_rank: int = 0


class RankRequest(BaseModel):
    user_id: str
    request_id: str | None = None
    candidates: list[RankCandidate]
    user_features: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, Any]:
    if not STATE.ready:
        raise HTTPException(status_code=503, detail="artifacts not loaded")
    return {
        "status": "ready",
        "als": STATE.als is not None,
        "ranker": STATE.ranker is not None,
        "model_version": STATE.model_version,
    }


@app.post("/internal/candidates")
def candidates(req: CandidateRequest) -> dict[str, Any]:
    t0 = time.perf_counter()
    if STATE.popularity is None:
        raise HTTPException(status_code=503, detail="popularity artifacts missing")
    cold = STATE.als is None or req.user_id not in (STATE.als.user_map if STATE.als else {})
    cands = retrieve_for_user(
        req.user_id,
        STATE.als,
        STATE.popularity,
        k=req.k,
        exclude=set(req.exclude),
        cold_start=cold,
    )
    for c in cands:
        meta = STATE.items.get(c["item_id"], {})
        c["title"] = meta.get("title")
        c["categories"] = meta.get("categories") or []
    return {
        "request_id": req.request_id,
        "user_id": req.user_id,
        "cold_start": cold,
        "candidates": cands,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
    }


@app.post("/internal/rank")
def rank(req: RankRequest) -> dict[str, Any]:
    t0 = time.perf_counter()
    if STATE.ranker is None:
        raise HTTPException(status_code=503, detail="ranker unavailable")
    ts = req.timestamp or datetime.now(UTC)
    state = UserFeatureState.from_dict(req.user_features) if req.user_features else UserFeatureState()
    X = []
    for c in req.candidates:
        meta = STATE.items.get(c.item_id, {})
        stats = STATE.item_stats.get(c.item_id, {})
        feats = build_ranker_features(
            retrieval_score=c.retrieval_score,
            source=c.source,
            source_rank=c.source_rank,
            user_state=state,
            item_id=c.item_id,
            item_meta=meta,
            item_stats=stats,
            timestamp=ts,
            previously_interacted=c.item_id in set(state.interacted_items),
        )
        X.append(feature_vector(feats))
    scores = predict_scores(STATE.ranker, X)
    ranked = []
    for c, score in zip(req.candidates, scores, strict=True):
        ranked.append(
            {
                "item_id": c.item_id,
                "source": c.source,
                "retrieval_score": c.retrieval_score,
                "source_rank": c.source_rank,
                "ranker_score": score,
                "title": STATE.items.get(c.item_id, {}).get("title"),
                "categories": STATE.items.get(c.item_id, {}).get("categories") or [],
            }
        )
    ranked.sort(key=lambda r: r["ranker_score"], reverse=True)
    return {
        "request_id": req.request_id,
        "user_id": req.user_id,
        "model_version": STATE.model_version,
        "ranked": ranked,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
    }


@app.get("/internal/items/{item_id}")
def item_meta(item_id: str) -> dict[str, Any]:
    meta = STATE.items.get(item_id)
    if not meta:
        raise HTTPException(status_code=404, detail="unknown item")
    return {"item_id": item_id, **meta}


@app.get("/internal/debug/user/{user_id}")
def debug_user(user_id: str, k: int = 10) -> dict[str, Any]:
    """Interview debug payload: retrieval vs ranker scores."""
    if STATE.popularity is None:
        raise HTTPException(status_code=503, detail="not ready")
    cands = retrieve_for_user(user_id, STATE.als, STATE.popularity, k=max(k, 20))
    dummy = RankRequest(user_id=user_id, candidates=[RankCandidate(**c) for c in cands])
    if STATE.ranker is None:
        return {"candidates": cands, "ranked": []}
    return rank(dummy)
