"""Download IMDb dumps and rebuild data/processed/imdb_movies.parquet."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from watchnext.catalog.imdb import refresh_imdb_parquet

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    dest = ROOT / "data" / "processed" / "imdb_movies.parquet"
    raw = ROOT / "data" / "raw" / "imdb"
    frame = refresh_imdb_parquet(dest, raw, now_year=date.today().year, force=args.force)
    print(f"wrote {dest} rows={frame.height} years={frame['year'].min()}-{frame['year'].max()}")


if __name__ == "__main__":
    main()
