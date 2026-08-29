# Experimentation

This is a hash bucketer, not an experiment platform.

```
bucket = uint64(sha256(experiment_id + ":" + user_id)[:8]) % 100
0-49  control     → ALS/retrieval order
50-99 treatment   → LightGBM ranker
```

Same user always lands in the same variant for a given experiment id. No `math/rand`, no process-level shuffle.

Responses and impression payloads include `experiment` and `model_version`.

## Shadow (optional)

`SHADOW_ENABLED=true` runs the ranker asynchronously on **control** traffic and records top-K overlap in `watchnext_shadow_topk_overlap`. Shadow scores never replace the user-visible list.
