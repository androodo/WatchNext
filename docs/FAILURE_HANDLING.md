# Failure handling

The recommendation API is written to return a feed when it can, and to fail loudly when it must not lie.

## Serving (GET /v1/recommendations)

| Failure | Behavior | Flags |
|---|---|---|
| Ranker 5xx / timeout | Order candidates by retrieval score | `fallback_used`, `ranker_unavailable` |
| Candidate service down | Empty candidate list (no invented items) | `candidate_service_unavailable` |
| Redis down | Empty user features, still retrieve if ML is up | `redis_unavailable` |

Downstream calls use `context.WithTimeout`. The parent request deadline is 800ms by default. Client disconnect cancels the request context.

## Events (POST /v1/events)

Publish failure → **503**. Never `202` for an event that did not reach Redpanda.

Impressions are best-effort and asynchronous. A failed impression does not fail the recommendation response.

## Health

- `GET /health` — process is alive
- `GET /ready` — HTTP server will accept traffic (including degraded serving)

Degraded is still ready. A missing ranker is not "the process cannot run."

## Demo

`python scripts/demo_failure_fallback.py` stops `ml-service`, checks `fallback_used`, starts it again.
