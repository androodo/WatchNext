# Tradeoffs

| Choice | Why | Cost |
|---|---|---|
| Redpanda instead of Kafka | One container, Kafka protocol | Not what most companies run in prod |
| Redis JSON blobs | Easy to inspect and demo | Not a feature store; no point-in-time online store |
| Shared Python feature engine | Parity | Go serving still depends on the consumer being up |
| Dedupe SET-before-write | Avoid double-counting | Can drop an event if Redis dies mid-update |
| Uniform negative samples | Honest given MovieLens | Ranker does not learn from impressions |
| Ranker trained on 800 users | Laptop runtime | Not the full train population |
| Two candidate sources | Enough to show two-stage ranking | No ANN, no two-tower |
| Compose, not Kubernetes | Local demo | No scheduler story |
| At-least-once + idempotency | Accurate language | Not exactly-once |

MovieLens 1M is ratings, not a feed. Mapping stars onto like/skip is a convenience. Real feed events (impression, dwell, skip) would change both labels and negatives.
