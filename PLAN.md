# Watch Next — Project Plan

Real-time personalized recommendation platform.

One sentence: like or skip a movie, and the next recommendations change immediately
via Redpanda, Redis, and a two-stage retrieval + ranker.

---

## Phase 0 — Architecture

### Canonical domain

Internal types are content-agnostic. MovieLens is only the development dataset.

| Domain | Meaning | MovieLens mapping |
|---|---|---|
| User | Person receiving a feed | `UserID` |
| Item | Recommendable content | `MovieID` + title + genres |
| Interaction | Behavioral event | rating converted to event + strength |
| Category | Item taxonomy | movie genres |

### Canonical interaction / event schema (v1)

```json
{
  "event_id": "uuid-v4",
  "schema_version": 1,
  "user_id": "42",
  "item_id": "123",
  "event_type": "like",
  "timestamp": "2000-12-31T22:12:40Z",
  "value": 1.0,
  "request_id": null,
  "metadata": {}
}
```

Required: `event_id`, `schema_version`, `user_id`, `item_id`, `event_type`, `timestamp`.

Event types: `impression`, `view`, `like`, `skip`, `watch`, `dislike`, `rating`.

MovieLens ratings become interactions:

| Rating | event_type | value |
|---|---|---|
| 5 | like | 1.0 |
| 4 | watch | 0.8 |
| 3 | view | 0.4 |
| 2 | skip | -0.3 |
| 1 | dislike | -1.0 |

### Service boundaries

Four runtime pieces. Not a microservice zoo.

| Component | Language | Responsibility |
|---|---|---|
| recommendation-api | Go | Public HTTP, orchestration, Redis, Kafka publish, experiments, fallbacks, metrics |
| ml_service | Python FastAPI | Candidate retrieval + ranker inference |
| feature_consumer | Python | Consume events, dedupe, update Redis features, dead-letter |
| web | Next.js | Demo UI only |

Infrastructure: Redis, Redpanda, Prometheus, Grafana.

Offline training is batch Python (`watchnext` + `scripts/`). It is not a service.

### Recommendation request lifecycle

```
GET /v1/recommendations/{user_id}?limit=10
  1. request_id
  2. experiment assignment (stable hash)
  3. Redis user features          [timeout]
  4. ML candidates                [timeout]
  5. ranker (treatment) or retrieval-order (control)
  6. filter (dedupe, disliked)
  7. top-K response
  8. async impression publish
```

### Failure behavior

| Dependency | Serving behavior | Response flags |
|---|---|---|
| Ranker down | Candidates ordered by retrieval_score | `fallback_used`, `ranker_unavailable` |
| Candidate service down | Cached popularity list | `candidate_service_unavailable` |
| Redis down | Non-personalized popularity | `redis_unavailable` |
| Event publish fail (POST /v1/events) | HTTP 503, never pretend success | — |
| Impression publish fail | Log + metric; still return recommendations | — |

### Feature semantics (shared)

One engine: `watchnext/features/engine.py`.

Used by:

- offline feature generation
- online feature consumer
- parity tests

**Event weights**

| event_type | weight |
|---|---|
| impression | 0.0 |
| view | 0.4 |
| like | 1.0 |
| watch | 0.8 |
| skip | -0.3 |
| dislike | -1.0 |
| rating | `(value - 3) / 2` |

**Category affinity (EMA)**

For each category on the item:

```
affinity[c] = (1 - α) * affinity[c] + α * weight
α = 0.15
```

Then L1-normalize positive mass; keep signed affinities clipped to `[-1, 1]`.

**Windowed counts**

Replay a capped recent-history buffer (max 500 events) and count events with
`timestamp >= now - window`. Windows: 24h, 7d.

**Online Redis keys**

- `user:{id}:features` — JSON feature blob
- `user:{id}:history` — recent events for windowed recount
- `processed_event:{event_id}` — dedupe key, TTL 7 days
- `item:{id}:features` — optional item counters
- `fallback:popularity` — cached popularity candidate list

### Model artifacts

```
artifacts/
  candidates/als.npz, popularity.parquet, mappings.json
  ranker/ranker-v1.txt, feature_names.json, metadata.json
  items/items.parquet
```

Never commit MovieLens raw files. Lightweight CI fixtures live under `tests/fixtures/`.

### Primary technical risks

| Risk | Mitigation |
|---|---|
| Time leakage | Temporal split + tests that assert `train.max_ts < val.min_ts < test.min_ts` |
| Training-serving skew | Shared feature engine + `tests/parity/` |
| Duplicate events | Redis `processed_event:{id}` + integration test |
| Stale online features | `feature_updated_at` + freshness histogram |
| Downstream hangs | `context.Context` + per-dependency timeouts |
| Model failure | Retrieval-score fallback, `fallback_used` |
| Consumer failure | At-least-once + idempotent updates + dead-letter topic |

Delivery semantics: **at-least-once** Kafka-compatible processing with **idempotent
consumers**. Not exactly-once.

---

## Phase status

| Phase | Name | Status |
|---|---|---|
| 0 | Design | complete |
| 1 | Offline recommender | complete |
| 2 | Learned ranker | complete |
| 3 | Online serving | complete |
| 4 | Real-time events | complete |
| 5 | Feedback loop | complete |
| 6 | Reliability | complete |
| 7 | Experimentation | complete |
| 8 | Observability | complete |
| 9 | Benchmarks | commands ready; fill reports by running harness against a live API |
| 10 | Simple UI | complete |

---

## Local ports

| Service | Port |
|---|---|
| recommendation-api | 8080 |
| ml_service | 8090 |
| feature_consumer health | 8091 |
| Redis | 6379 |
| Redpanda Kafka API | 19092 |
| Redpanda Admin | 9644 |
| Prometheus | 9090 |
| Grafana | 3001 |
| web | 3000 |
