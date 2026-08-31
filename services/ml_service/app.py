"""Load artifacts and serve candidates + ranking. Internal API only."""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from watchnext.candidates.als import ALSModel, load_als
from watchnext.candidates.popularity import load_popularity
from watchnext.candidates.retrieve import retrieve_for_user
from watchnext.catalog.browse import (
    CatalogRow,
    build_catalog,
    fill_by_genre,
    genres_with_counts,
    normalize_genre,
    search_catalog,
)
from watchnext.catalog.categories import load_item_categories
from watchnext.catalog.imdb import load_imdb_parquet, merge_imdb_into_items, refresh_imdb_parquet
from watchnext.catalog.live import blend_live_catalog, recency_boost
from watchnext.common.constants import CANDIDATE_K, MAX_CANDIDATE_K
from watchnext.features.engine import UserFeatureState
from watchnext.features.names import feature_vector
from watchnext.online.processor import FeatureProcessor
from watchnext.ranking.dataset import build_ranker_features
from watchnext.ranking.train import load_ranker, predict_scores

log = structlog.get_logger("ml_service")

ROOT = Path(os.environ.get("WATCHNEXT_ROOT", Path(__file__).resolve().parents[2]))
ARTIFACTS = Path(os.environ.get("WATCHNEXT_ARTIFACTS", ROOT / "artifacts"))
PROCESSED = Path(os.environ.get("WATCHNEXT_PROCESSED", ROOT / "data" / "processed"))


class AppState:
    als: ALSModel | None = None
    popularity: Any = None
    ranker: Any = None
    items: dict[str, dict[str, Any]]
    item_stats: dict[str, dict[str, float]]
    catalog: list[CatalogRow]
    model_version: str = "ranker-v1"
    ready: bool = False
    live_items: int = 0
    year_min: int | None = None
    year_max: int | None = None
    catalog_updated_at: str | None = None
    processor: Any = None

    def __init__(self) -> None:
        self.items = {}
        self.item_stats = {}
        self.catalog = []
        self.live_items = 0
        self.year_min = None
        self.year_max = None
        self.catalog_updated_at = None
        self.processor = None


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
    _merge_live_catalog(download=False)
    STATE.ready = STATE.popularity is not None or bool(STATE.items)
    log.info(
        "ml_artifacts_loaded",
        als=STATE.als is not None,
        ranker=STATE.ranker is not None,
        items=len(STATE.items),
        catalog=len(STATE.catalog),
        live_items=STATE.live_items,
        year_max=STATE.year_max,
        ready=STATE.ready,
    )


def _catalog_years() -> tuple[int | None, int | None]:
    years = [row.year for row in STATE.catalog if row.year is not None]
    if not years:
        return None, None
    return min(years), max(years)


def _rebuild_catalog() -> None:
    STATE.catalog = build_catalog(STATE.items, STATE.item_stats)
    STATE.live_items = sum(1 for row in STATE.catalog if row.item_id.startswith("tt"))
    STATE.year_min, STATE.year_max = _catalog_years()


def _merge_live_catalog(*, download: bool) -> None:
    imdb_path = PROCESSED / "imdb_movies.parquet"
    raw_dir = ROOT / "data" / "raw" / "imdb"
    if download:
        frame = refresh_imdb_parquet(imdb_path, raw_dir, now_year=date.today().year, force=True)
    else:
        frame = load_imdb_parquet(imdb_path)
    if frame is None:
        _rebuild_catalog()
        return
    STATE.items, STATE.item_stats, added = merge_imdb_into_items(STATE.items, STATE.item_stats, frame)
    _rebuild_catalog()
    meta_path = imdb_path.with_suffix(".json")
    if meta_path.exists():
        try:
            STATE.catalog_updated_at = json.loads(meta_path.read_text(encoding="utf-8")).get("updated_at")
        except json.JSONDecodeError:
            STATE.catalog_updated_at = None
    log.info("imdb_catalog_merged", added=added, catalog=len(STATE.catalog), live=STATE.live_items)


def _init_processor() -> None:
    url = os.environ.get("REDIS_URL", "")
    if not url:
        return
    try:
        from redis import Redis

        client = Redis.from_url(url, decode_responses=True)
        client.ping()
        STATE.processor = FeatureProcessor(client, load_item_categories(ROOT))
        log.info("feature_processor_ready")
    except Exception as exc:
        log.warning("feature_processor_unavailable", error=str(exc))
        STATE.processor = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _load()
    _init_processor()
    yield


app = FastAPI(title="Watch Next ML Service", lifespan=lifespan)


class CandidateRequest(BaseModel):
    user_id: str
    request_id: str | None = None
    k: int = CANDIDATE_K
    exclude: list[str] = Field(default_factory=list)
    genre: str = ""
    affinities: dict[str, float] = Field(default_factory=dict)


class RankCandidate(BaseModel):
    item_id: str
    source: str = "als"
    retrieval_score: float = 0.0
    source_rank: int = 0
    popularity: float = 0.0


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
        "catalog": len(STATE.catalog),
        "live_items": STATE.live_items,
        "year_max": STATE.year_max,
    }


@app.get("/internal/catalog")
def catalog(
    q: str = "",
    genre: str = "",
    sort: str = "popular",
    offset: int = 0,
    limit: int = 48,
    year_min: int | None = None,
    year_max: int | None = None,
) -> dict[str, Any]:
    if not STATE.catalog:
        raise HTTPException(status_code=503, detail="catalog not loaded")
    items, total = search_catalog(
        STATE.catalog,
        query=q,
        genre=genre,
        sort=sort,
        offset=offset,
        limit=limit,
        year_min=year_min if year_min and year_min > 0 else None,
        year_max=year_max if year_max and year_max > 0 else None,
    )
    return {
        "items": items,
        "total": total,
        "offset": max(0, offset),
        "limit": min(max(1, limit), 100),
        "query": q,
        "genre": normalize_genre(genre),
        "sort": sort if sort in {"popular", "year", "title"} else "popular",
    }


@app.get("/internal/genres")
def genres() -> dict[str, Any]:
    return {
        "genres": genres_with_counts(STATE.catalog),
        "total_items": len(STATE.catalog),
        "live_items": STATE.live_items,
        "year_min": STATE.year_min,
        "year_max": STATE.year_max,
        "updated_at": STATE.catalog_updated_at,
    }


@app.post("/internal/catalog/refresh")
def refresh_catalog() -> dict[str, Any]:
    try:
        _merge_live_catalog(download=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"imdb_refresh_failed: {exc}") from exc
    body = genres()
    body["status"] = "ok"
    return body


@app.post("/internal/ingest")
def ingest(payload: dict[str, Any]) -> dict[str, Any]:
    if STATE.processor is None:
        raise HTTPException(status_code=503, detail="feature processor unavailable")
    result = STATE.processor.process_payload(payload)
    if result.status == "invalid":
        raise HTTPException(status_code=400, detail=result.reason or "invalid event")
    return {"status": result.status, "event_id": result.event_id}


@app.post("/internal/candidates")
def candidates(req: CandidateRequest) -> dict[str, Any]:
    t0 = time.perf_counter()
    if STATE.popularity is None and not STATE.catalog:
        raise HTTPException(status_code=503, detail="popularity artifacts missing")
    cold = STATE.als is None or req.user_id not in (STATE.als.user_map if STATE.als else {})
    k = min(max(req.k, 1), MAX_CANDIDATE_K)
    cands: list[dict[str, Any]] = []
    if STATE.popularity is not None:
        cands = retrieve_for_user(
            req.user_id,
            STATE.als,
            STATE.popularity,
            k=k,
            exclude=set(req.exclude),
            cold_start=cold,
        )
    for c in cands:
        meta = STATE.items.get(c["item_id"], {})
        stats = STATE.item_stats.get(c["item_id"]) or {}
        c["title"] = meta.get("title")
        c["categories"] = meta.get("categories") or []
        if meta.get("year") is not None:
            c["year"] = meta.get("year")
        if not c.get("popularity"):
            c["popularity"] = float(stats.get("popularity") or 0.0)
    cands = blend_live_catalog(
        cands,
        STATE.catalog,
        k=k,
        affinities=req.affinities,
        exclude=set(req.exclude),
        genre=req.genre,
    )
    if req.genre and len(cands) < k:
        cands = fill_by_genre(cands, STATE.catalog, req.genre, k)
    return {
        "request_id": req.request_id,
        "user_id": req.user_id,
        "cold_start": cold,
        "genre": normalize_genre(req.genre),
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
    now_year = date.today().year
    ranked = []
    for c, score in zip(req.candidates, scores, strict=True):
        meta = STATE.items.get(c.item_id, {})
        year = meta.get("year")
        stats = STATE.item_stats.get(c.item_id) or {}
        ranked.append(
            {
                "item_id": c.item_id,
                "source": c.source,
                "retrieval_score": c.retrieval_score,
                "source_rank": c.source_rank,
                "ranker_score": float(score) + 0.55 * recency_boost(year, now_year),
                "title": meta.get("title"),
                "categories": meta.get("categories") or [],
                "year": year,
                "popularity": float(stats.get("popularity") or c.popularity or 0.0),
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
    stats = STATE.item_stats.get(item_id) or {}
    return {
        "item_id": item_id,
        "title": meta.get("title"),
        "categories": meta.get("categories") or [],
        "year": meta.get("year"),
        "rating": float(stats.get("avg") or 0.0),
        "popularity": float(stats.get("popularity") or 0.0),
        "source": "imdb" if str(item_id).startswith("tt") else "catalog",
    }


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
