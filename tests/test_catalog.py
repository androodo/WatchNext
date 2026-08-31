from __future__ import annotations

from watchnext.catalog.browse import (
    CatalogRow,
    canonicalize_genres,
    fill_by_genre,
    genres_with_counts,
    search_catalog,
)


def _rows() -> list[CatalogRow]:
    return [
        CatalogRow("1", "Matrix, The (1999)", "matrix, the (1999)", ("sci_fi", "action"), 1999, 1.0, 4.5),
        CatalogRow("2", "American Beauty (1999)", "american beauty (1999)", ("drama", "comedy"), 1999, 0.8, 4.2),
        CatalogRow("3", "Fargo (1996)", "fargo (1996)", ("crime", "drama"), 1996, 0.6, 4.1),
        CatalogRow("4", "Toy Story (1995)", "toy story (1995)", ("animation", "childrens"), 1995, 0.9, 4.0),
    ]


def test_normalize_genre_accepts_human_labels():
    assert canonicalize_genres(["Science Fiction", "Action film"]) == ["sci_fi", "action"]
    assert canonicalize_genres(["absurdist fiction"]) == []


def test_search_filters_title_and_genre():
    page, total = search_catalog(_rows(), query="matrix", genre="sci_fi")
    assert total == 1
    assert page[0]["item_id"] == "1"


def test_search_ignores_hyphens_and_articles():
    rows = _rows() + [
        CatalogRow("tt0145487", "Spider-Man (2002)", "spider-man (2002)", ("action",), 2002, 0.7, 4.0),
        CatalogRow("tt0371746", "Iron Man (2008)", "iron man (2008)", ("action",), 2008, 0.65, 4.0),
        CatalogRow("tt0120903", "X-Men (2000)", "x-men (2000)", ("action",), 2000, 0.5, 3.8),
    ]
    spider, spider_n = search_catalog(rows, query="spiderman")
    iron, iron_n = search_catalog(rows, query="ironman")
    xmen, xmen_n = search_catalog(rows, query="xmen")
    matrix, matrix_n = search_catalog(rows, query="the matrix")
    assert spider_n == 1 and spider[0]["item_id"] == "tt0145487"
    assert iron_n == 1 and iron[0]["item_id"] == "tt0371746"
    assert xmen_n == 1 and xmen[0]["item_id"] == "tt0120903"
    assert matrix_n == 1 and matrix[0]["item_id"] == "1"


def test_search_filters_year_window():
    page, total = search_catalog(_rows(), year_min=1999, year_max=1999)
    assert total == 2
    assert {row["item_id"] for row in page} == {"1", "2"}


def test_search_sorts_by_year():
    page, total = search_catalog(_rows(), sort="year", limit=10, now_year=1999)
    assert total == 4
    assert page[0]["item_id"] == "1"
    assert [row["item_id"] for row in page] == ["1", "2", "4", "3"]


def test_newest_sort_keeps_known_hits_ahead_of_obscure_new_titles():
    rows = [
        CatalogRow("obscure", "Fjord (2026)", "fjord (2026)", ("drama",), 2026, 0.22, 0.0),
        CatalogRow("coming", "The Odyssey (2026)", "the odyssey (2026)", ("action",), 2026, 0.52, 0.0),
        CatalogRow("recent", "Oppenheimer (2023)", "oppenheimer (2023)", ("drama",), 2023, 0.66, 0.0),
        CatalogRow("hit", "Avengers: Endgame (2019)", "avengers: endgame (2019)", ("action",), 2019, 0.74, 0.0),
    ]
    page, total = search_catalog(rows, sort="year", limit=10, now_year=2026)
    ids = [row["item_id"] for row in page]
    assert total == 4
    assert ids[0] == "coming"
    assert ids.index("recent") < ids.index("obscure")
    assert ids.index("hit") < ids.index("obscure")


def test_genre_counts():
    counts = {row["name"]: row["count"] for row in genres_with_counts(_rows())}
    assert counts["drama"] == 2
    assert counts["sci_fi"] == 1


def test_fill_by_genre_keeps_hits_then_backfills_catalog():
    existing = [{"item_id": "9", "categories": ["comedy"], "source": "als"}]
    filled = fill_by_genre(existing, _rows(), "drama", k=3)
    assert filled[0]["item_id"] == "2"
    assert {row["item_id"] for row in filled} <= {"2", "3"}
    assert len(filled) == 2


def test_load_item_categories_merges_json(tmp_path, monkeypatch):
    monkeypatch.delenv("WATCHNEXT_ITEM_CATEGORIES", raising=False)
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "item_categories.json").write_text('{"10": ["sci_fi"], "tt1": ["adventure"]}', encoding="utf-8")
    from watchnext.catalog.categories import load_item_categories

    cats = load_item_categories(tmp_path)
    assert cats["10"] == ["sci_fi"]
    assert cats["tt1"] == ["adventure"]
