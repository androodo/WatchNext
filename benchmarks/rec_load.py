#!/usr/bin/env python
"""Recommendation API load benchmark. Writes reports/benchmark_results.json from measurements."""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("API_URL", "http://localhost:8080")
USER = os.environ.get("BENCH_USER", "42")


def one_request() -> tuple[float, int, bool]:
    t0 = time.perf_counter()
    with urlopen(f"{API}/v1/recommendations/{USER}?limit=10", timeout=5) as resp:
        body = json.loads(resp.read().decode())
        latency = time.perf_counter() - t0
        return latency, resp.status, bool(body.get("fallback_used"))


def bench(concurrency: int, n: int) -> dict:
    latencies: list[float] = []
    errors = 0
    fallbacks = 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(one_request) for _ in range(n)]
        for fut in as_completed(futs):
            try:
                latency, status, fb = fut.result()
                latencies.append(latency)
                if status >= 400:
                    errors += 1
                if fb:
                    fallbacks += 1
            except Exception:
                errors += 1
    elapsed = time.perf_counter() - t0
    latencies.sort()

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(round(p * (len(latencies) - 1))))
        return latencies[idx]

    return {
        "concurrency": concurrency,
        "requests": n,
        "ok": len(latencies),
        "errors": errors,
        "error_rate": errors / n if n else 0,
        "fallback_rate": fallbacks / n if n else 0,
        "elapsed_s": round(elapsed, 4),
        "rps": round((n - errors) / elapsed, 2) if elapsed else 0,
        "p50_s": round(pct(0.50), 4),
        "p95_s": round(pct(0.95), 4),
        "p99_s": round(pct(0.99), 4),
        "mean_s": round(statistics.mean(latencies), 4) if latencies else None,
    }


def main() -> None:
    levels = [int(x) for x in os.environ.get("BENCH_CONCURRENCY", "1,10,25").split(",")]
    n = int(os.environ.get("BENCH_N", "80"))
    results = []
    for c in levels:
        print(f"concurrency={c} n={n}")
        row = bench(c, n)
        print(row)
        results.append(row)
    payload = {
        "measured_at": datetime.now(UTC).isoformat(),
        "target": API,
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "cpu": platform.processor(),
            "machine": platform.machine(),
        },
        "recommendation_api": results,
        "note": "Local-machine numbers. Not production scale.",
    }
    out = ROOT / "reports" / "benchmark_results.json"
    existing = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing.update(payload)
    out.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    md = ROOT / "reports" / "BENCHMARKS.md"
    lines = [
        "# Benchmarks",
        "",
        "Generated from `python benchmarks/rec_load.py`. Do not edit numbers by hand.",
        "",
        f"- Measured at: {payload['measured_at']}",
        f"- OS: {payload['environment']['os']}",
        f"- Python: {payload['environment']['python']}",
        "",
        "## Recommendation API",
        "",
        "| Concurrency | RPS | p50 (s) | p95 (s) | p99 (s) | error rate | fallback rate |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['concurrency']} | {row['rps']} | {row['p50_s']} | {row['p95_s']} | {row['p99_s']} "
            f"| {row['error_rate']:.3f} | {row['fallback_rate']:.3f} |"
        )
    lines += ["", "These are **local** measurements, not a capacity claim.", ""]
    # Keep stream section if present.
    if "stream" in existing:
        s = existing["stream"]
        lines += [
            "## Stream processing",
            "",
            f"- Events: {s.get('n_events')}",
            f"- Events/sec: {s.get('events_per_sec')}",
            f"- Feature update p50/p95 (s): {s.get('p50_s')} / {s.get('p95_s')}",
            "",
        ]
    md.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
