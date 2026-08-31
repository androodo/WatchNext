"""Blend current-year titles into the retrieval shortlist."""

from __future__ import annotations

from datetime import date
from typing import Any

from watchnext.catalog.browse import CatalogRow, normalize_genre


def recency_boost(year: int | None, now_year: int | None = None) -> float:
    """0 at 2000, 1 at the current year. Older titles stay at 0."""
    if year is None:
        return 0.0
    now = now_year or date.today().year
    span = max(1, now - 2000)
    return max(0.0, min(1.25, (int(year) - 2000) / span))


def _affinity(categories: tuple[str, ...] | list[str], affinities: dict[str, float] | None) -> float:
    if not affinities or not categories:
        return 0.0
    hits = [float(affinities.get(normalize_genre(c), 0.0) or 0.0) for c in categories]
    if not hits:
        return 0.0
    return sum(hits) / len(hits)


def live_score(
    row: CatalogRow,
    affinities: dict[str, float] | None,
    now_year: int | None = None,
) -> float:
    return 0.45 * row.popularity + 0.40 * recency_boost(row.year, now_year) + 0.15 * _affinity(row.categories, affinities)


def blend_live_catalog(
    existing: list[dict[str, Any]],
    rows: list[CatalogRow],
    *,
    k: int,
    affinities: dict[str, float] | None = None,
    exclude: set[str] | None = None,
    genre: str = "",
    now_year: int | None = None,
    live_from_year: int = 2001,
) -> list[dict[str, Any]]:
    """Keep retrieval hits, then interleave post-2000 titles so the bill is not stuck in 1999."""
    banned = exclude or set()
    g = normalize_genre(genre)
    now = now_year or date.today().year
    seen: set[str] = set()
    classic: list[dict[str, Any]] = []
    for cand in existing:
        iid = str(cand.get("item_id") or "")
        if not iid or iid in banned or iid in seen:
            continue
        cats = [normalize_genre(c) for c in (cand.get("categories") or [])]
        if g and g not in cats:
            continue
        seen.add(iid)
        classic.append(cand)

    live_rows = [
        row
        for row in rows
        if row.item_id not in seen
        and row.item_id not in banned
        and row.year is not None
        and row.year >= live_from_year
        and (not g or g in row.categories)
    ]
    live_rows.sort(key=lambda r: live_score(r, affinities, now), reverse=True)
    live = [row.as_dict(source="imdb" if row.item_id.startswith("tt") else "catalog") for row in live_rows]

    out: list[dict[str, Any]] = []
    i = j = 0
    prefer_live_first = True
    while len(out) < k and (i < len(live) or j < len(classic)):
        take_live = prefer_live_first
        prefer_live_first = not prefer_live_first
        if take_live and i < len(live):
            out.append(live[i])
            i += 1
            continue
        if j < len(classic):
            out.append(classic[j])
            j += 1
            continue
        if i < len(live):
            out.append(live[i])
            i += 1
    return out[:k]
