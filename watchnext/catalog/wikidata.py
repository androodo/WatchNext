"""Wikidata live catalog when IMDb dumps are blocked. Wikidata updates continuously."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any

import polars as pl

SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "WatchNext/0.1 (educational recommender; https://localhost)"


def _query(sparql: str, timeout: int = 90) -> dict[str, Any]:
    data = urllib.parse.urlencode({"query": sparql}).encode()
    req = urllib.request.Request(
        SPARQL,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _year_query(year: int, min_sitelinks: int) -> str:
    return f"""
SELECT ?imdb ?title ?sitelinks (GROUP_CONCAT(DISTINCT ?genreLabel; separator=",") AS ?genres)
WHERE {{
  ?film wdt:P31 wd:Q11424 .
  ?film wdt:P345 ?imdb .
  ?film wdt:P577 ?date .
  ?film rdfs:label ?title .
  ?film wikibase:sitelinks ?sitelinks .
  FILTER(LANG(?title) = "en")
  FILTER(?sitelinks >= {min_sitelinks})
  FILTER(YEAR(?date) = {year})
  OPTIONAL {{
    ?film wdt:P136 ?genre .
    ?genre rdfs:label ?genreLabel .
    FILTER(LANG(?genreLabel) = "en")
  }}
}}
GROUP BY ?imdb ?title ?sitelinks
LIMIT 1200
"""


def rows_from_bindings(bindings: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in bindings:
        imdb = (row.get("imdb") or {}).get("value") or ""
        title = (row.get("title") or {}).get("value") or ""
        if not imdb.startswith("tt") or not title or imdb in seen:
            continue
        seen.add(imdb)
        sitelinks = int(float((row.get("sitelinks") or {}).get("value") or 0))
        genres = (row.get("genres") or {}).get("value") or ""
        out.append(
            {
                "tconst": imdb,
                "primaryTitle": title,
                "year": year,
                "genres": genres,
                "votes": max(sitelinks, 1) * 1000,
                "rating": 7.0,
            }
        )
    return out


def fetch_wikidata_movies(now_year: int, *, from_year: int = 2001) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in range(from_year, now_year + 1):
        min_links = 8 if year >= now_year - 2 else 14
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                payload = _query(_year_query(year, min_links))
                bindings = payload.get("results", {}).get("bindings", [])
                rows.extend(rows_from_bindings(bindings, year))
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        if last_err is not None:
            continue
        time.sleep(0.35)
    if not rows:
        raise RuntimeError("wikidata returned no films")
        return pl.DataFrame(
            schema={
                "tconst": pl.Utf8,
                "primaryTitle": pl.Utf8,
                "year": pl.Int32,
                "genres": pl.Utf8,
                "votes": pl.Int64,
                "rating": pl.Float64,
            }
        )
    return pl.DataFrame(rows).unique(subset=["tconst"], keep="first")
