"""MovieLens 1M → canonical User / Item / Interaction tables."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from pulserank_ml.common.schema import new_event

RATING_TO_EVENT = {
    5: ("like", 1.0),
    4: ("watch", 0.8),
    3: ("view", 0.4),
    2: ("skip", -0.3),
    1: ("dislike", -1.0),
}


def _read_sep_file(path: Path, columns: list[str]) -> pl.DataFrame:
    rows: list[list[str]] = []
    text = path.read_text(encoding="latin-1")
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("::")
        if len(parts) != len(columns):
            raise ValueError(f"expected {len(columns)} fields in {path}, got {len(parts)}: {line[:80]}")
        rows.append(parts)
    return pl.DataFrame(rows, schema=columns, orient="row")


def load_raw_movielens(raw_dir: Path) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    base = raw_dir / "ml-1m"
    if not (base / "ratings.dat").exists():
        # downloaded zip may extract to raw_dir/ml-1m or files may sit in raw_dir
        if (raw_dir / "ratings.dat").exists():
            base = raw_dir
        else:
            raise FileNotFoundError(f"MovieLens files not found under {raw_dir}")
    movies = _read_sep_file(base / "movies.dat", ["item_id", "title", "genres"])
    ratings = _read_sep_file(base / "ratings.dat", ["user_id", "item_id", "rating", "timestamp"])
    users = _read_sep_file(base / "users.dat", ["user_id", "gender", "age", "occupation", "zip_code"])
    return movies, ratings, users


def parse_year(title: str) -> int | None:
    title = title.strip()
    if len(title) >= 6 and title.endswith(")") and title[-5:-1].isdigit():
        return int(title[-5:-1])
    return None


def to_canonical(
    movies: pl.DataFrame,
    ratings: pl.DataFrame,
    users: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    items = movies.with_columns(
        pl.col("item_id").cast(pl.Utf8),
        pl.col("title").cast(pl.Utf8),
        pl.col("genres")
        .str.split("|")
        .list.eval(pl.element().str.replace_all("'", "").str.replace_all("-", "_").str.to_lowercase())
        .alias("categories"),
        pl.col("title").map_elements(parse_year, return_dtype=pl.Int32).alias("year"),
    ).select("item_id", "title", "categories", "year")

    users_out = users.select(pl.col("user_id").cast(pl.Utf8))

    rating_int = ratings.with_columns(pl.col("rating").cast(pl.Int32))
    events = []
    types = []
    values = []
    for r in rating_int["rating"].to_list():
        et, val = RATING_TO_EVENT[int(r)]
        events.append(et)
        types.append(et)
        values.append(val)

    interactions = ratings.with_columns(
        pl.col("user_id").cast(pl.Utf8),
        pl.col("item_id").cast(pl.Utf8),
        pl.col("rating").cast(pl.Float64),
        pl.col("timestamp").cast(pl.Int64),
        pl.Series("event_type", types),
        pl.Series("value", values),
    ).select("user_id", "item_id", "event_type", "timestamp", "value", "rating")

    return users_out, items, interactions


def interactions_as_events(interactions: pl.DataFrame) -> list:
    from datetime import UTC, datetime

    out = []
    for row in interactions.iter_rows(named=True):
        ts = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
        out.append(
            new_event(
                user_id=row["user_id"],
                item_id=row["item_id"],
                event_type=row["event_type"],
                timestamp=ts,
                value=float(row["value"]),
                event_id=f"ml1m-{row['user_id']}-{row['item_id']}-{row['timestamp']}",
            )
        )
    return out
