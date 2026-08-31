"""Normalize titles so MovieLens 'Matrix, The (1999)' matches IMDb 'The Matrix'."""

from __future__ import annotations

import re

_ARTICLES = ("the", "a", "an")
_YEAR_TAIL = re.compile(r"\s*\((\d{4})\)\s*$")
_PARENS_TAIL = re.compile(r"\s*\([^)]*\)\s*$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_year(title: str) -> tuple[str, int | None]:
    raw = (title or "").strip()
    match = _YEAR_TAIL.search(raw)
    if not match:
        return raw, None
    return raw[: match.start()].strip(), int(match.group(1))


def canonical_title(title: str) -> str:
    name, _ = strip_year(title)
    name = _PARENS_TAIL.sub("", name).strip().lower()
    name = _NON_ALNUM.sub(" ", name).strip()
    for article in _ARTICLES:
        prefix = f"{article} "
        suffix = f" {article}"
        if name.startswith(prefix):
            name = name[len(prefix) :].strip()
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def compact_title(title: str) -> str:
    """Letters and digits only so 'spiderman' matches 'Spider-Man'."""
    return _NON_ALNUM.sub("", (title or "").lower())


def display_title(title: str, year: int | None) -> str:
    name, parsed_year = strip_year(title)
    name = _PARENS_TAIL.sub("", name).strip() or title.strip()
    yr = year if year is not None else parsed_year
    if yr is None:
        return name
    return f"{name} ({yr})"
