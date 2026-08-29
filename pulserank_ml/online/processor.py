"""Apply a validated event to Redis-backed online features. Idempotent on event_id."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pulserank_ml.common.constants import DEDUPE_TTL_SECONDS
from pulserank_ml.common.schema import InteractionEvent, parse_event
from pulserank_ml.features.engine import FeatureEngine, HistoryRecord, UserFeatureState


class RedisLike(Protocol):
    def get(self, name: str) -> bytes | str | None: ...
    def set(self, name: str, value: Any, ex: int | None = None, nx: bool = False) -> Any: ...


@dataclass
class ProcessResult:
    status: str  # applied | duplicate | invalid
    event_id: str | None = None
    user_id: str | None = None
    reason: str | None = None
    state: UserFeatureState | None = None


def user_features_key(user_id: str) -> str:
    return f"user:{user_id}:features"


def user_history_key(user_id: str) -> str:
    return f"user:{user_id}:history"


def processed_key(event_id: str) -> str:
    return f"processed_event:{event_id}"


class FeatureProcessor:
    def __init__(
        self,
        redis: RedisLike,
        item_categories: dict[str, list[str]],
        dedupe_ttl: int = DEDUPE_TTL_SECONDS,
    ) -> None:
        self.redis = redis
        self.item_categories = item_categories
        self.dedupe_ttl = dedupe_ttl

    def process_payload(self, payload: dict[str, Any], now: datetime | None = None) -> ProcessResult:
        try:
            event = parse_event(payload)
        except Exception as exc:
            return ProcessResult(status="invalid", reason=str(exc))
        return self.process_event(event, now=now)

    def process_event(self, event: InteractionEvent, now: datetime | None = None) -> ProcessResult:
        claimed = self.redis.set(processed_key(event.event_id), "1", ex=self.dedupe_ttl, nx=True)
        if not claimed:
            return ProcessResult(
                status="duplicate",
                event_id=event.event_id,
                user_id=event.user_id,
                reason="duplicate_event_id",
            )
        state = self._apply(event, now=now or datetime.now(UTC))
        return ProcessResult(
            status="applied",
            event_id=event.event_id,
            user_id=event.user_id,
            state=state,
        )

    def _apply(self, event: InteractionEvent, now: datetime) -> UserFeatureState:
        raw_feat = self.redis.get(user_features_key(event.user_id))
        raw_hist = self.redis.get(user_history_key(event.user_id))
        history: list[HistoryRecord] = []
        affinities: dict[str, float] = {}
        interaction_count = 0
        engagement_sum = 0.0
        disliked: list[str] = []
        interacted: list[str] = []
        if raw_feat:
            data = json.loads(raw_feat)
            state0 = UserFeatureState.from_dict(data)
            affinities = state0.affinities
            interaction_count = state0.interaction_count
            engagement_sum = state0.engagement_sum
            disliked = state0.disliked_items
            interacted = state0.interacted_items
        if raw_hist:
            history = FeatureEngine.history_from_docs(json.loads(raw_hist))
        engine = FeatureEngine(
            history=history,
            affinities=affinities,
            interaction_count=interaction_count,
            engagement_sum=engagement_sum,
            disliked_items=disliked,
            interacted_items=interacted,
        )
        cats = self.item_categories.get(str(event.item_id), [])
        state = engine.apply(event, cats, now=now)
        self.redis.set(user_features_key(event.user_id), json.dumps(state.to_dict()))
        self.redis.set(user_history_key(event.user_id), json.dumps(engine.export_history()))
        return state


class MemoryRedis:
    """Test double. SET NX matches Redis semantics enough for dedupe tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.store.get(name)

    def set(self, name: str, value: Any, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and name in self.store:
            return False
        self.store[name] = value if isinstance(value, str) else str(value)
        return True
