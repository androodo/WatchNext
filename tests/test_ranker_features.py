from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pulserank_ml.common.schema import new_event
from pulserank_ml.features.engine import FeatureEngine
from pulserank_ml.features.names import RANKER_FEATURES, feature_vector
from pulserank_ml.ranking.dataset import build_ranker_features


def test_feature_vector_length_stable():
    eng = FeatureEngine()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    state = eng.apply(new_event("u", "i", "like", timestamp=t0, event_id="1"), ["sci_fi"])
    feats = build_ranker_features(
        retrieval_score=0.8,
        source="als",
        source_rank=3,
        user_state=state,
        item_id="i2",
        item_meta={"categories": ["sci_fi"], "year": 1999},
        item_stats={"popularity": 0.2, "avg": 0.5, "count": 10, "like_rate": 0.4},
        timestamp=t0 + timedelta(hours=1),
        previously_interacted=False,
    )
    vec = feature_vector(feats)
    assert len(vec) == len(RANKER_FEATURES)
    assert 15 <= len(RANKER_FEATURES) <= 30
    assert feats["source_is_als"] == 1.0
    assert feats["user_item_affinity"] == state.item_affinity(["sci_fi"])
