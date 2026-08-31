from __future__ import annotations

from pathlib import Path

import polars as pl

from watchnext.catalog.imdb import build_imdb_frame, merge_imdb_into_items
from watchnext.catalog.wikidata import rows_from_bindings
from watchnext.catalog.live import blend_live_catalog, recency_boost
from watchnext.catalog.browse import CatalogRow
from watchnext.catalog.titles import canonical_title, display_title


def test_wikidata_bindings_dedupe_and_keep_tt_ids():
    rows = rows_from_bindings(
        [
            {
                "imdb": {"value": "tt15398776"},
                "title": {"value": "Oppenheimer"},
                "sitelinks": {"value": "80"},
                "genres": {"value": "drama,history"},
            },
            {
                "imdb": {"value": "tt15398776"},
                "title": {"value": "Oppenheimer"},
                "sitelinks": {"value": "80"},
            },
            {"imdb": {"value": "Q1"}, "title": {"value": "Not IMDb"}},
        ],
        2023,
    )
    assert len(rows) == 1
    assert rows[0]["tconst"] == "tt15398776"
    assert rows[0]["year"] == 2023
    assert rows[0]["votes"] == 80000
    assert canonical_title("Matrix, The (1999)") == canonical_title("The Matrix")
    assert canonical_title("American Beauty (1999)") == "american beauty"
    assert display_title("Oppenheimer", 2023) == "Oppenheimer (2023)"


def test_recency_boost_is_zero_before_2001():
    assert recency_boost(1999, now_year=2026) == 0.0
    assert recency_boost(2026, now_year=2026) == 1.0
    assert recency_boost(2013, now_year=2026) > 0.4


def test_blend_live_catalog_interleaves_new_titles():
    classic = [
        {
            "item_id": "1",
            "title": "American Beauty (1999)",
            "categories": ["drama"],
            "year": 1999,
            "source": "popularity",
        }
    ]
    rows = [
        CatalogRow("1", "American Beauty (1999)", "american beauty (1999)", ("drama",), 1999, 1.0, 4.0),
        CatalogRow("tt15398776", "Oppenheimer (2023)", "oppenheimer (2023)", ("drama", "history"), 2023, 0.9, 4.3),
        CatalogRow("tt1517268", "Barbie (2023)", "barbie (2023)", ("comedy", "adventure"), 2023, 0.8, 3.8),
    ]
    blended = blend_live_catalog(classic, rows, k=3, now_year=2026)
    ids = [row["item_id"] for row in blended]
    assert ids[0].startswith("tt")
    assert "1" in ids
    assert "tt15398776" in ids or "tt1517268" in ids


def test_build_imdb_frame_keeps_recent_low_vote_films(tmp_path: Path):
    basics = tmp_path / "title.basics.tsv.gz"
    ratings = tmp_path / "title.ratings.tsv.gz"
    basics_txt = tmp_path / "title.basics.tsv"
    ratings_txt = tmp_path / "title.ratings.tsv"
    basics_txt.write_text(
        "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\tstartYear\tendYear\truntimeMinutes\tgenres\n"
        "tt0000001\tmovie\tOld Silent\tOld Silent\t0\t1920\t\\N\t\\N\tDrama\n"
        "tt0111161\tmovie\tThe Shawshank Redemption\tThe Shawshank Redemption\t0\t1994\t\\N\t\\N\tDrama\n"
        "tt15398776\tmovie\tOppenheimer\tOppenheimer\t0\t2023\t\\N\t\\N\tBiography,Drama,History\n"
        "tt9999999\tmovie\tObscure New Film\tObscure New Film\t0\t2026\t\\N\t\\N\tDrama\n"
        "tt8888888\ttvSeries\tNot A Movie\tNot A Movie\t0\t2024\t\\N\t\\N\tDrama\n",
        encoding="utf-8",
    )
    ratings_txt.write_text(
        "tconst\taverageRating\tnumVotes\n"
        "tt0000001\t6.0\t10\n"
        "tt0111161\t9.3\t2800000\n"
        "tt15398776\t8.3\t800000\n"
        "tt9999999\t7.1\t120\n"
        "tt8888888\t8.0\t50000\n",
        encoding="utf-8",
    )
    import gzip

    for src, dest in ((basics_txt, basics), (ratings_txt, ratings)):
        with src.open("rb") as fh, gzip.open(dest, "wb") as out:
            out.write(fh.read())

    frame = build_imdb_frame(basics, ratings, now_year=2026, min_votes=1500, recent_min_votes=80, recent_years=2)
    ids = set(frame["tconst"].to_list())
    assert "tt0111161" in ids
    assert "tt15398776" in ids
    assert "tt9999999" in ids  # 2026 with 120 votes
    assert "tt0000001" not in ids  # 10 votes, not recent enough
    assert "tt8888888" not in ids


def test_merge_keeps_movielens_id_on_title_match():
    items = {
        "318": {"title": "Shawshank Redemption, The (1994)", "categories": ["drama"], "year": 1994},
    }
    stats = {"318": {"popularity": 0.2, "avg": 4.5, "count": 2000.0, "like_rate": 0.4}}
    imdb = pl.DataFrame(
        {
            "tconst": ["tt0111161", "tt15398776"],
            "primaryTitle": ["The Shawshank Redemption", "Oppenheimer"],
            "year": [1994, 2023],
            "genres": ["Drama", "Biography,Drama,History"],
            "votes": [2_800_000, 800_000],
            "rating": [9.3, 8.3],
        }
    )
    merged, merged_stats, added = merge_imdb_into_items(items, stats, imdb)
    assert "318" in merged
    assert "tt0111161" not in merged
    assert "tt15398776" in merged
    assert added == 1
    assert merged["tt15398776"]["year"] == 2023
    assert merged_stats["318"]["popularity"] > 0
