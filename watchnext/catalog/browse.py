"""Search and filter the full item catalog (not just the retrieval shortlist)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from watchnext.catalog.titles import canonical_title, compact_title


def normalize_genre(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.strip().lower().replace(" ", "_").replace("-", "_").replace("'", "")


_GENRE_NEEDLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sci_fi", ("sci_fi", "science_fiction", "scifi")),
    ("film_noir", ("film_noir", "noir")),
    ("childrens", ("childrens", "children", "family", "kids")),
    ("musical", ("musical",)),
    ("animation", ("animation", "animated", "anime")),
    ("documentary", ("documentary",)),
    ("adventure", ("adventure",)),
    ("thriller", ("thriller",)),
    ("romance", ("romance", "romantic")),
    ("mystery", ("mystery",)),
    ("fantasy", ("fantasy",)),
    ("horror", ("horror",)),
    ("comedy", ("comedy",)),
    ("crime", ("crime", "gangster")),
    ("western", ("western",)),
    ("action", ("action",)),
    ("drama", ("drama",)),
    ("war", ("war",)),
)


def canonicalize_genres(raw: Iterable[str] | str | None) -> list[str]:
    if not raw:
        return []
    parts = [raw] if isinstance(raw, str) else list(raw)
    blob = " ".join(normalize_genre(p).replace("_", " ") for p in parts if p)
    padded = f" {blob} "
    out: list[str] = []
    for canon, needles in _GENRE_NEEDLES:
        if any(f" {n.replace('_', ' ')} " in padded for n in needles):
            out.append(canon)
    return out


@dataclass(frozen=True)
class CatalogRow:
    item_id: str
    title: str
    title_lc: str
    categories: tuple[str, ...]
    year: int | None
    popularity: float
    avg: float

    def as_dict(self, source: str = "catalog") -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "categories": list(self.categories),
            "year": self.year,
            "popularity": self.popularity,
            "rating": self.avg,
            "source": source,
            "retrieval_score": self.popularity,
            "source_rank": 0,
        }


def build_catalog(items: dict[str, dict[str, Any]], item_stats: dict[str, dict[str, float]]) -> list[CatalogRow]:
    rows: list[CatalogRow] = []
    for item_id, meta in items.items():
        title = str(meta.get("title") or item_id)
        cats = tuple(normalize_genre(c) for c in (meta.get("categories") or []) if c)
        stats = item_stats.get(item_id) or {}
        year = meta.get("year")
        rows.append(
            CatalogRow(
                item_id=str(item_id),
                title=title,
                title_lc=title.lower(),
                categories=cats,
                year=int(year) if year is not None else None,
                popularity=float(stats.get("popularity") or 0.0),
                avg=float(stats.get("avg") or 0.0),
            )
        )
    rows.sort(key=lambda r: (-r.popularity, r.title_lc))
    return rows


def genres_with_counts(rows: Iterable[CatalogRow]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(row.categories)
    return [{"name": name, "count": counts[name]} for name in sorted(counts)]


def _matches(row: CatalogRow, query: str, genre: str) -> bool:
    if genre and genre not in row.categories:
        return False
    if not query:
        return True
    if query in row.title_lc:
        return True
    compact_q = compact_title(query)
    if compact_q and compact_q in compact_title(row.title):
        return True
    canon_q = canonical_title(query)
    return bool(canon_q and canon_q in canonical_title(row.title))


def newest_score(row: CatalogRow, now_year: int | None = None) -> float:
    """Newest first, but unknown new titles do not bury movies people actually know."""
    now = now_year or date.today().year
    recency = 0.0 if row.year is None else 0.9 ** max(0, now - int(row.year))
    return 0.40 * recency + 0.60 * row.popularity


def search_catalog(
    rows: list[CatalogRow],
    *,
    query: str = "",
    genre: str = "",
    sort: str = "popular",
    offset: int = 0,
    limit: int = 48,
    year_min: int | None = None,
    year_max: int | None = None,
    now_year: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    q = (query or "").strip().lower()
    g = normalize_genre(genre)
    matched = [row for row in rows if _matches(row, q, g)]
    if year_min is not None:
        matched = [row for row in matched if row.year is not None and row.year >= year_min]
    if year_max is not None:
        matched = [row for row in matched if row.year is not None and row.year <= year_max]
    if sort == "title":
        matched.sort(key=lambda r: r.title_lc)
    elif sort == "year":
        matched.sort(key=lambda r: (-newest_score(r, now_year), r.title_lc))
    else:
        matched.sort(key=lambda r: (-r.popularity, r.title_lc))
    offset = max(0, offset)
    limit = min(max(1, limit), 100)
    page = [row.as_dict() for row in matched[offset : offset + limit]]
    return page, len(matched)


def fill_by_genre(
    existing: list[dict[str, Any]],
    rows: list[CatalogRow],
    genre: str,
    k: int,
) -> list[dict[str, Any]]:
    """Keep retrieval hits that match the genre, then fill from the full catalog."""
    g = normalize_genre(genre)
    if not g:
        return existing[:k]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for cand in existing:
        cats = [normalize_genre(c) for c in (cand.get("categories") or [])]
        if g not in cats:
            continue
        iid = str(cand["item_id"])
        if iid in seen:
            continue
        seen.add(iid)
        out.append(cand)
        if len(out) >= k:
            return out
    for row in rows:
        if g not in row.categories or row.item_id in seen:
            continue
        seen.add(row.item_id)
        out.append(row.as_dict())
        if len(out) >= k:
            break
    return out
