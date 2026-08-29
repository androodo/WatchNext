# Training–serving parity

**Training-serving skew** is when a feature means one thing when you fit the model and another thing when you score traffic. The ranker then sees a different world than the one it was trained on. Quality drops quietly. Dashboards still look healthy.

PulseRank avoids two independent formulas for the same name.

| Path | Code |
|---|---|
| Offline point-in-time features | `FeatureEngine.apply` in `pulserank_ml/ranking/dataset.py` |
| Online stream updates | `FeatureProcessor` → same `FeatureEngine` |
| Parity test | `tests/parity/test_feature_parity.py` |

The test replays:

view sci-fi, view sci-fi, like sci-fi, skip comedy

through a single incremental engine and through `replay()`, and asserts the snapshots match.

What this does **not** prove: Redis serialization bugs, clock differences between 24h windows online vs offline, or that production traffic matches MovieLens rating→event mapping.

What it does prove: affinity EMA, weights, and window recounts are not forked.
