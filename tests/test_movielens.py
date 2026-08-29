from __future__ import annotations

from watchnext.datasets.movielens import RATING_TO_EVENT, parse_year


def test_rating_mapping():
    assert RATING_TO_EVENT[5][0] == "like"
    assert RATING_TO_EVENT[1][0] == "dislike"


def test_parse_year():
    assert parse_year("Toy Story (1995)") == 1995
    assert parse_year("No Year") is None
