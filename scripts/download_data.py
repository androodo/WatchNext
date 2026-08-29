#!/usr/bin/env python
"""Download MovieLens 1M into data/raw/. Do not commit the dataset."""

from __future__ import annotations

import io
import ssl
import zipfile
from pathlib import Path
from urllib.request import urlopen

URL = "https://files.grouplens.org/datasets/movielens/ml-1m.zip"
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw"


def _fetch(url: str) -> bytes:
    try:
        ctx = ssl.create_default_context()
        with urlopen(url, timeout=180, context=ctx) as resp:
            return resp.read()
    except Exception as first:
        print(f"verified TLS failed ({first}); retrying without verification")
        ctx = ssl._create_unverified_context()
        with urlopen(url, timeout=180, context=ctx) as resp:
            return resp.read()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    ratings = DEST / "ml-1m" / "ratings.dat"
    if ratings.exists():
        print(f"already present: {ratings}")
        return
    print(f"downloading {URL}")
    payload = _fetch(URL)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(DEST)
    if not ratings.exists():
        raise SystemExit(f"expected {ratings} after extract")
    print(f"extracted to {DEST / 'ml-1m'}")


if __name__ == "__main__":
    main()
