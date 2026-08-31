"""item_id → genres for the feature consumer (MovieLens JSON plus live overlay)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from watchnext.catalog.browse import canonicalize_genres


def processed_dir(root: Path | None = None) -> Path:
    base = root or Path(os.environ.get("WATCHNEXT_ROOT", Path(__file__).resolve().parents[2]))
    return base / "data" / "processed"


def _as_genres(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return canonicalize_genres([str(x) for x in raw if x])
    if isinstance(raw, str):
        return canonicalize_genres(raw.split(","))
    return []


def load_item_categories(root: Path | None = None) -> dict[str, list[str]]:
    processed = processed_dir(root)
    out: dict[str, list[str]] = {}
    cat_path = Path(os.environ.get("WATCHNEXT_ITEM_CATEGORIES", processed / "item_categories.json"))
    if cat_path.exists():
        raw = json.loads(cat_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            for key, value in raw.items():
                cats = _as_genres(value)
                if cats:
                    out[str(key)] = cats

    parquet_specs = (
        ("items.parquet", "item_id", "categories"),
        ("imdb_movies.parquet", "tconst", "genres"),
    )
    for name, id_col, genre_col in parquet_specs:
        path = processed / name
        if not path.exists():
            continue
        try:
            import polars as pl

            frame = pl.read_parquet(path)
        except Exception:
            continue
        if id_col not in frame.columns:
            continue
        for row in frame.iter_rows(named=True):
            item_id = str(row.get(id_col) or "")
            if not item_id or item_id in out:
                continue
            cats = _as_genres(row.get(genre_col))
            if cats:
                out[item_id] = cats
    return out
