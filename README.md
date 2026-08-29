# PulseRank

Real-time personalized recommendations. User interactions stream through Kafka-compatible Redpanda, update online features in Redis, and immediately change the next ranking from a two-stage retrieval + ranker.

**UI:** [http://localhost:3000](http://localhost:3000) · **API:** `GET /v1/recommendations/{user_id}`

## Features

- **Two-stage ranking** — ALS + popularity retrieve ~100 candidates; LightGBM LambdaMART re-ranks on ~21 features (retrieval score, user windows, item stats, category affinity)
- **Live feedback loop** — like / skip events update Redis user features before the next request
- **Training–serving parity** — the same `FeatureEngine` runs offline and online
- **A/B experiments** — stable hash assignment; impressions carry `experiment` and `model_version`
- **Graceful degradation** — per-dependency timeouts, ranker / candidate / Redis fallbacks, dead-letter for invalid events
- **Idempotent streaming** — at-least-once consumption with Redis `event_id` dedupe
- **Observability** — Prometheus metrics, Grafana dashboards, OpenTelemetry traces

## Architecture

```mermaid
flowchart LR
  Client --> GoAPI[Go API]
  GoAPI --> Redis
  GoAPI --> ML[Python ML service]
  ML --> Retrieve[ALS + popularity]
  ML --> Rank[LightGBM]
  GoAPI --> Redpanda
  Redpanda --> Consumer[Feature consumer]
  Consumer --> Redis
```

[Architecture](docs/ARCHITECTURE.md) · [Event pipeline](docs/EVENT_PIPELINE.md) · [Recommendation system](docs/RECOMMENDATION_SYSTEM.md) · [Features](docs/FEATURES.md)

## How it works

1. Assign the user to an experiment variant.
2. Load online features from Redis.
3. Retrieve candidates (ALS + popularity).
4. Rank with LightGBM (treatment) or retrieval order (control).
5. Filter duplicates and disliked items; return top 10.
6. Publish the impression; later likes/skips flow:

```
POST /v1/events → Redpanda → feature consumer → Redis → next GET /v1/recommendations
```

## Evaluation

MovieLens 1M, temporal split (80% train / 10% val / 10% test), 400 test users. Full report: [reports/offline_evaluation.md](reports/offline_evaluation.md).

| Method | NDCG@10 | HitRate@10 | MRR |
|---|---:|---:|---:|
| random | 0.010 | 0.093 | 0.027 |
| popularity | 0.103 | 0.455 | 0.183 |
| ALS | 0.141 | 0.545 | 0.269 |
| ALS + ranker | **0.165** | **0.628** | **0.295** |

Candidate Recall@100: popularity 0.203 → ALS 0.253.

## Performance

| Concurrency | RPS | p50 | p95 | p99 |
|---:|---:|---:|---:|---:|
| 1 | 37 | 31 ms | 35 ms | 68 ms |
| 10 | 112 | 83 ms | 109 ms | 118 ms |

Full table: [reports/BENCHMARKS.md](reports/BENCHMARKS.md).

## Quick start

Requires Python 3.12+, Go 1.24+, Docker.

```bash
python -m pip install -e ".[dev]"
python scripts/download_data.py
python scripts/prepare_data.py
python scripts/train.py
python scripts/evaluate.py
docker compose up -d --build
python scripts/seed_online_features.py
curl http://localhost:8080/v1/recommendations/1001?limit=10
python scripts/demo_realtime_personalization.py 1001
```

Makefile: `setup`, `download-data`, `prepare-data`, `train`, `evaluate`, `up`, `down`, `test`, `lint`, `demo`, `benchmark`.

## Repository

| Path | Role |
|---|---|
| `cmd/recommendation-api` | Go HTTP API |
| `internal/` | Orchestration, experiments, events, telemetry |
| `services/ml_service` | Candidate retrieval + ranking |
| `services/feature_consumer` | Stream → Redis features |
| `pulserank_ml/` | Data, features, ALS, ranker, metrics |
| `web/` | Next.js UI |
| `tests/parity/` | Offline / online feature equality |
