# Benchmarks

Generated from `python benchmarks/rec_load.py` and `python benchmarks/stream_load.py`. Do not edit numbers by hand.

- Measured at: 2026-08-29T11:24:19Z
- OS: Windows-11-10.0.26200-SP0
- Python: 3.13.1
- CPU: Intel64 Family 6 Model 154 Stepping 3, GenuineIntel

## Recommendation API

| Concurrency | RPS | p50 (s) | p95 (s) | p99 (s) | error rate | fallback rate |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 36.92 | 0.0312 | 0.0349 | 0.0683 | 0.000 | 0.000 |
| 10 | 111.61 | 0.0831 | 0.109 | 0.1175 | 0.000 | 0.000 |

## Stream processing

- Events published: 200
- Publish throughput: 38.04 events/sec
- Applied by consumer: 200
- End-to-end consume throughput: 18.04 events/sec

These are **local** measurements, not a capacity claim.
