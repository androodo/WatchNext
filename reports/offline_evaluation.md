# Offline evaluation

Generated from `scripts/evaluate.py`. Do not edit numbers by hand.

- Dataset: `MovieLens 1M`
- Train interactions: 800164
- Val interactions: 100023
- Test interactions: 100022
- Test users evaluated: 400
- Catalog size: 3883

## Candidate retrieval

| Source | Recall@50 | Recall@100 | HitRate@50 | HitRate@100 |
|---|---:|---:|---:|---:|
| popularity | 0.1249 | 0.2026 | 0.7650 | 0.8325 |
| als | 0.1577 | 0.2528 | 0.8225 | 0.8925 |

## Ranking (feed metrics on test positives)

| Method | Precision@10 | Recall@10 | NDCG@10 | MRR | HitRate@10 | Coverage@10 |
|---|---:|---:|---:|---:|---:|---:|
| random | 0.0108 | 0.0013 | 0.0103 | 0.0268 | 0.0925 | 0.6351 |
| popularity | 0.1037 | 0.0292 | 0.1034 | 0.1829 | 0.4550 | 0.0026 |
| als | 0.1308 | 0.0384 | 0.1407 | 0.2689 | 0.5450 | 0.2014 |
| als+ranker | 0.1565 | 0.0476 | 0.1646 | 0.2951 | 0.6275 | 0.1053 |

## Notes

- Split is **temporal** (earliest 80% train, next 10% val, latest 10% test).
- Test labels are positive events (`like`, `watch`) after the train cutoff.
- Random baseline uses a fixed seed.
- ALS + ranker reranks ALS/popularity candidates; it does not score the full catalog.
