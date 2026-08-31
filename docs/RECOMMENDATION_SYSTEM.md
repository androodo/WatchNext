# Recommendation system

Two stages, kept separate on purpose.

```
catalog (MovieLens + IMDb) → candidate generation → ranker → recency / genre → top 36
```

## Candidates

1. **Popularity** — positive interaction counts in the train window. Cold start and fallback.
2. **ALS** — user/item factors. Personalized retrieval. Uses the `implicit` library when installed; otherwise a NumPy Hu–Koren–Volinsky ALS.

Candidates carry `item_id`, `source`, `retrieval_score`, `source_rank`.

## Ranker

LightGBM `LGBMRanker` with `objective=lambdarank`. Features are listed in `watchnext/features/names.py` (~21 fields). Online serving builds the same vector via `build_ranker_features`.

## Labels and negatives

A positive is `like` or `watch` at time t. Features use only interactions **before** t.

Negatives are uniform samples from items the user had not interacted with before t. **Unobserved is not dislike.** This over-represents random catalog items and under-represents impressed-but-ignored items (MovieLens has no impressions). Documented limitation.

## Temporal split

Earliest 80% of timestamps → train, next 10% → val, latest 10% → test. Tests in `tests/test_temporal_split.py` fail the build if a later split leaks into an earlier one.

Random shuffles of history would let the model train on the future. That metric would look better and be wrong.

## Cold start

Unknown users skip ALS and receive popularity. Unseen items can still appear via popularity if they have train support; brand-new items have no ALS factor.

## Filtering

After ranking: drop duplicate `item_id`, drop `disliked_items` from the user feature blob. An optional `genre` query keeps only matching categories and backfills from the full catalog so a comedy bill is not stuck at three hits. Filtering is not folded into the model score.

## Catalog

`GET /v1/catalog?q=&genre=&sort=popular|year|title&limit=&offset=` pages the whole item table. `GET /v1/genres` returns category counts. MovieLens 1M stops in 2000; IMDb’s public dump (refreshed with `POST /v1/catalog/refresh`) adds later titles. ALS still personalizes the overlap with MovieLens. New titles are mixed in by popularity, recency, and genre affinity.
