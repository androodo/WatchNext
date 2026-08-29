# Benchmarking

Commands:

```
python benchmarks/rec_load.py
python benchmarks/stream_load.py
```

Outputs:

- `reports/benchmark_results.json`
- `reports/BENCHMARKS.md` (generated from JSON)

Until those scripts run against a live stack, the reports say **Not yet measured.**

Numbers are from the machine that ran the harness. They are not a capacity plan.

Environment fields (OS, Python, CPU when the OS exposes it) are stored next to the timings.

k6/Vegeta are fine substitutes; the included harness is stdlib + threads so the repo does not require extra binaries.
