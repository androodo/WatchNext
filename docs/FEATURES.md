# Features

One engine: `pulserank_ml/features/engine.py`.

The feature consumer, offline ranker dataset, and parity tests all call it. Do not reimplement `sci_fi` affinity in Go or in a notebook.

## Event weights

| type | weight |
|---|---|
| impression | 0 |
| view | 0.4 |
| like | 1.0 |
| watch | 0.8 |
| skip | -0.3 |
| dislike | -1.0 |
| rating | `(value - 3) / 2` |

## Category affinity

For each category on the item, if `|weight| > 0`:

```
affinity[c] = (1 - 0.15) * affinity[c] + 0.15 * weight
```

Clipped to `[-1, 1]`.

Serving also applies a **0.35 affinity overlay** on the ranker (or retrieval) score:

`score += 0.35 * mean(user affinity for the item's categories)`

That is a serving-time mix, not a second model. It is how a like on sci-fi can move the next feed without retraining LightGBM.

## Windows

Recent history (cap 500) is recounted at `as_of`:

- 24h: views/likes/skips/watches
- 7d: same

Online `as_of` is wall clock at apply time. Offline `as_of` is the prediction timestamp.

## Redis

- `user:{id}:features` JSON blob
- `user:{id}:history` capped event list
- `processed_event:{id}` dedupe
- `fallback:popularity` optional cached ids

## Ranker inputs

Retrieval metadata + user windows + item popularity/rating stats + `user_item_affinity` (mean of the user's affinities on the item's categories) + coarse time features. See `RANKER_FEATURES`.
