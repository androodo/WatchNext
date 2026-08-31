"""IMDb non-commercial dumps → current movie catalog (refreshed daily by IMDb)."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from watchnext.catalog.browse import canonicalize_genres
from watchnext.catalog.titles import canonical_title, display_title
from watchnext.catalog.wikidata import fetch_wikidata_movies

BASICS_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"
RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WatchNext/0.1 catalog-refresh"


def _download(url: str, dest: Path, timeout: int = 20) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as fh:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)


def ensure_dumps(raw_dir: Path, *, force: bool = False) -> tuple[Path, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    basics = raw_dir / "title.basics.tsv.gz"
    ratings = raw_dir / "title.ratings.tsv.gz"
    if force or not basics.exists():
        _download(BASICS_URL, basics)
    if force or not ratings.exists():
        _download(RATINGS_URL, ratings)
    return basics, ratings


def _scan_tsv(path: Path) -> pl.LazyFrame:
    return pl.scan_csv(
        path,
        separator="\t",
        null_values=["\\N"],
        infer_schema_length=0,
        quote_char=None,
        encoding="utf8-lossy",
    )


def build_imdb_frame(
    basics_path: Path,
    ratings_path: Path,
    *,
    now_year: int,
    min_votes: int = 1500,
    recent_min_votes: int = 80,
    recent_years: int = 2,
) -> pl.DataFrame:
    basics = _scan_tsv(basics_path).select(
        "tconst",
        "titleType",
        "primaryTitle",
        "isAdult",
        "startYear",
        "genres",
    )
    ratings = _scan_tsv(ratings_path).select("tconst", "averageRating", "numVotes")
    recent_from = now_year - recent_years
    movies = (
        basics.filter(pl.col("titleType") == "movie")
        .filter((pl.col("isAdult") == "0") | pl.col("isAdult").is_null())
        .filter(pl.col("startYear").is_not_null())
        .join(ratings, on="tconst", how="inner")
        .with_columns(
            pl.col("startYear").cast(pl.Int32, strict=False).alias("year"),
            pl.col("numVotes").cast(pl.Int64, strict=False).alias("votes"),
            pl.col("averageRating").cast(pl.Float64, strict=False).alias("rating"),
        )
        .filter(pl.col("year").is_not_null())
        .filter(pl.col("year") <= now_year)
        .filter(pl.col("year") >= 1915)
        .filter(pl.col("votes").is_not_null())
        .filter(
            (pl.col("votes") >= min_votes) | ((pl.col("year") >= recent_from) & (pl.col("votes") >= recent_min_votes))
        )
        .select("tconst", "primaryTitle", "year", "genres", "votes", "rating")
        .collect()
    )
    return movies


def refresh_imdb_parquet(
    dest: Path,
    raw_dir: Path,
    *,
    now_year: int,
    force: bool = False,
) -> pl.DataFrame:
    source = "wikidata"
    basics = raw_dir / "title.basics.tsv.gz"
    ratings = raw_dir / "title.ratings.tsv.gz"
    frame: pl.DataFrame | None = None
    if basics.exists() and ratings.exists():
        try:
            frame = build_imdb_frame(basics, ratings, now_year=now_year)
            source = "imdb"
        except Exception:
            frame = None
    if force and (frame is None or not basics.exists()):
        try:
            basics, ratings = ensure_dumps(raw_dir, force=True)
            frame = build_imdb_frame(basics, ratings, now_year=now_year)
            source = "imdb"
        except Exception:
            frame = None
    if frame is None or frame.height == 0:
        source = "wikidata"
        frame = fetch_wikidata_movies(now_year)
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(dest)
    meta = {
        "updated_at": datetime.now(UTC).isoformat(),
        "rows": frame.height,
        "year_max": int(frame["year"].max()) if frame.height else None,
        "year_min": int(frame["year"].min()) if frame.height else None,
        "source": source,
    }
    dest.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return frame


def load_imdb_parquet(path: Path) -> pl.DataFrame | None:
    if not path.exists():
        return None
    return pl.read_parquet(path)


def _imdb_stats_row(votes: int, rating: float | None, max_votes: float) -> dict[str, float]:
    votes = max(int(votes), 0)
    rating = float(rating or 0.0)
    return {
        "popularity": (votes / max_votes) if max_votes else 0.0,
        "avg": rating / 2.0 if rating else 0.0,
        "count": float(min(votes / 50.0, 4000.0)),
        "like_rate": 0.12,
    }


def merge_imdb_into_items(
    items: dict[str, dict[str, Any]],
    item_stats: dict[str, dict[str, float]],
    imdb: pl.DataFrame,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, float]], int]:
    """Keep MovieLens ids when titles match; add the rest as tt… ids."""
    index: dict[tuple[str, int | None], str] = {}
    names: dict[str, str] = {}
    for item_id, meta in items.items():
        year = meta.get("year")
        year_i = int(year) if year is not None else None
        key_name = canonical_title(str(meta.get("title") or ""))
        index[(key_name, year_i)] = item_id
        names[key_name] = item_id

    max_votes = float(imdb["votes"].max() or 1) if imdb.height else 1.0
    added = 0
    for row in imdb.iter_rows(named=True):
        year = int(row["year"])
        title = str(row["primaryTitle"] or "")
        key = (canonical_title(title), year)
        genres_raw = str(row.get("genres") or "")
        categories = canonicalize_genres(genres_raw.split(","))
        stats = _imdb_stats_row(int(row["votes"] or 0), row.get("rating"), max_votes)
        existing_id = index.get(key) or names.get(canonical_title(title))
        if existing_id:
            prev = item_stats.get(existing_id) or {}
            if stats["popularity"] > float(prev.get("popularity") or 0.0):
                merged = dict(prev)
                merged["popularity"] = stats["popularity"]
                item_stats[existing_id] = merged
            continue
        iid = str(row["tconst"])
        items[iid] = {
            "title": display_title(title, year),
            "categories": categories,
            "year": year,
        }
        item_stats[iid] = stats
        index[key] = iid
        added += 1

    max_pop = max((float(v.get("popularity") or 0.0) for v in item_stats.values()), default=1.0) or 1.0
    for stats in item_stats.values():
        stats["popularity"] = float(stats.get("popularity") or 0.0) / max_pop
    return items, item_stats, added
