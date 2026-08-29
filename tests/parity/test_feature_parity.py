from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pulserank_ml.common.schema import new_event
from pulserank_ml.features.engine import FeatureEngine


def test_offline_replay_matches_online_incremental():
    """Training-serving parity: same ordered history → same features."""
    t0 = datetime(2024, 6, 1, tzinfo=UTC)
    history = [
        (new_event("42", "10", "view", timestamp=t0, event_id="1"), ["sci_fi"]),
        (
            new_event("42", "11", "view", timestamp=t0 + timedelta(minutes=1), event_id="2"),
            ["sci_fi"],
        ),
        (
            new_event("42", "12", "like", timestamp=t0 + timedelta(minutes=2), event_id="3"),
            ["sci_fi"],
        ),
        (
            new_event("42", "20", "skip", timestamp=t0 + timedelta(minutes=3), event_id="4"),
            ["comedy"],
        ),
    ]

    online = FeatureEngine()
    for ev, cats in history:
        online.apply(ev, cats)

    offline = FeatureEngine()
    offline_state = offline.replay(history, as_of=t0 + timedelta(minutes=3))
    online_state = online.snapshot(t0 + timedelta(minutes=3))

    assert online_state.to_dict() == offline_state.to_dict()
    assert online_state.affinity("sci_fi") > online_state.affinity("comedy")
