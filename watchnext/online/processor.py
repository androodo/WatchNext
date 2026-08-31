"""Apply a validated event to Redis-backed online features. Idempotent on event_id."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from watchnext.catalog.browse import canonicalize_genres
from watchnext.common.constants import DEDUPE_TTL_SECONDS
from watchnext.common.schema import InteractionEvent, parse_event
from watchnext.features.engine import FeatureEngine, HistoryRecord, UserFeatureState


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
        liked: list[str] = []
        interacted: list[str] = []
        recent: list[dict[str, Any]] = []
        if raw_feat:
            data = json.loads(raw_feat)
            state0 = UserFeatureState.from_dict(data)
            affinities = state0.affinities
            interaction_count = state0.interaction_count
            engagement_sum = state0.engagement_sum
            disliked = state0.disliked_items
            liked = state0.liked_items
            interacted = state0.interacted_items
            recent = state0.recent_actions
        if raw_hist:
            history = FeatureEngine.history_from_docs(json.loads(raw_hist))
        engine = FeatureEngine(
            history=history,
            affinities=affinities,
            interaction_count=interaction_count,
            engagement_sum=engagement_sum,
            disliked_items=disliked,
            liked_items=liked,
            interacted_items=interacted,
            recent_actions=recent,
        )
        engine.seed_affinities_from_likes(self.item_categories)
        cats = self._categories_for(event)
        state = engine.apply(event, cats, now=now)
        self.redis.set(user_features_key(event.user_id), json.dumps(state.to_dict()))
        self.redis.set(user_history_key(event.user_id), json.dumps(engine.export_history()))
        return state

    def _categories_for(self, event: InteractionEvent) -> list[str]:
        mapped = list(self.item_categories.get(str(event.item_id), []) or [])
        if mapped:
            return mapped
        raw = (event.metadata or {}).get("categories") or []
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",") if part.strip()]
        return canonicalize_genres(raw)

    def backfill_user_affinities(self, features_key: str) -> bool:
        raw = self.redis.get(features_key)
        if not raw:
            return False
        data = json.loads(raw)
        if data.get("affinities"):
            return False
        liked = [str(i) for i in (data.get("liked_items") or [])]
        if not liked:
            return False
        engine = FeatureEngine(liked_items=liked)
        engine.seed_affinities_from_likes(self.item_categories)
        if not engine._affinities:
            return False
        data["affinities"] = {k: round(v, 6) for k, v in sorted(engine._affinities.items())}
        self.redis.set(features_key, json.dumps(data))
        return True


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
