#!/usr/bin/env python
"""Print stable A/B assignments for a few user ids."""

from __future__ import annotations

import hashlib
import struct
import sys


def assign(experiment_id: str, user_id: str) -> tuple[str, int]:
    digest = hashlib.sha256(f"{experiment_id}:{user_id}".encode()).digest()
    bucket = struct.unpack(">Q", digest[:8])[0] % 100
    variant = "control" if bucket < 50 else "treatment"
    return variant, int(bucket)


def main() -> None:
    exp = "ranker-vs-retrieval"
    users = sys.argv[1:] or [str(i) for i in range(1, 16)]
    print(f"experiment_id={exp}")
    for u in users:
        v, b = assign(exp, u)
        model = "als-retrieval" if v == "control" else "ranker-v1"
        print(f"user={u:4} bucket={b:02d} variant={v:10} model={model}")


if __name__ == "__main__":
    main()
