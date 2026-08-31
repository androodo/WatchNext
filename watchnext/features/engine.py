"""Canonical online/offline feature engine.

Training and serving MUST call this module. Do not reimplement affinity or
windowed counts elsewhere. See docs/TRAINING_SERVING_PARITY.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from watchnext.common.constants import (
    AFFINITY_ALPHA,
    HISTORY_CAP,
    NEGATIVE_EVENT_TYPES,
    POSITIVE_EVENT_TYPES,
    WINDOW_7D_SECONDS,
    WINDOW_24H_SECONDS,
)
from watchnext.common.schema import InteractionEvent

COUNT_EVENT_TYPES = ("view", "like", "skip", "watch")
RECENT_ACTIONS_CAP = 40


def _ts(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).timestamp()


@dataclass
class HistoryRecord:
    timestamp: float
    event_type: str
    item_id: str
    weight: float
    categories: list[str]


@dataclass
class UserFeatureState:
    views_24h: int = 0
    likes_24h: int = 0
    skips_24h: int = 0
    watches_24h: int = 0
    views_7d: int = 0
    likes_7d: int = 0
    skips_7d: int = 0
    watches_7d: int = 0
    interaction_count: int = 0
    engagement_sum: float = 0.0
    avg_engagement: float = 0.0
    affinities: dict[str, float] = field(default_factory=dict)
    last_activity_ts: float | None = None
    feature_updated_at: float | None = None
    disliked_items: list[str] = field(default_factory=list)
    liked_items: list[str] = field(default_factory=list)
    interacted_items: list[str] = field(default_factory=list)
    recent_actions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserFeatureState:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        state = cls(**filtered)
        state.affinities = dict(state.affinities)
        state.disliked_items = list(state.disliked_items)
        state.liked_items = list(state.liked_items)
        state.interacted_items = list(state.interacted_items)
        state.recent_actions = [dict(row) for row in state.recent_actions]
        return state

    def affinity(self, category: str) -> float:
        return float(self.affinities.get(category, 0.0))

    def item_affinity(self, categories: Iterable[str]) -> float:
        cats = list(categories)
        if not cats:
            return 0.0
        return sum(self.affinity(c) for c in cats) / len(cats)


class FeatureEngine:
    """Incremental feature store for a single user.

    Apply events in timestamp order. Windowed counts are recomputed against
    `as_of` (event time online; prediction time offline).
    """

    def __init__(
        self,
        history: list[HistoryRecord] | None = None,
        affinities: dict[str, float] | None = None,
        interaction_count: int = 0,
        engagement_sum: float = 0.0,
        disliked_items: list[str] | None = None,
        liked_items: list[str] | None = None,
        interacted_items: list[str] | None = None,
        recent_actions: list[dict[str, Any]] | None = None,
        alpha: float = AFFINITY_ALPHA,
        history_cap: int = HISTORY_CAP,
    ) -> None:
        self.history: list[HistoryRecord] = list(history or [])
        self._affinities: dict[str, float] = dict(affinities or {})
        self.interaction_count = interaction_count
        self.engagement_sum = engagement_sum
        self._disliked: list[str] = list(disliked_items or [])
        self._liked: list[str] = list(liked_items or [])
        self._interacted: list[str] = list(interacted_items or [])
        self._recent: list[dict[str, Any]] = [dict(row) for row in (recent_actions or [])]
        self._interacted_set: set[str] = set(self._interacted)
        self._disliked_set: set[str] = set(self._disliked)
        self._liked_set: set[str] = set(self._liked)
        self.alpha = alpha
        self.history_cap = history_cap

    @classmethod
    def from_state(
        cls,
        state: UserFeatureState,
        history: list[HistoryRecord] | None = None,
    ) -> FeatureEngine:
        return cls(
            history=history,
            affinities=state.affinities,
            interaction_count=state.interaction_count,
            engagement_sum=state.engagement_sum,
            disliked_items=state.disliked_items,
            liked_items=state.liked_items,
            interacted_items=state.interacted_items,
            recent_actions=state.recent_actions,
        )

    def seed_affinities_from_likes(self, item_categories: dict[str, list[str]]) -> None:
        """Fill empty affinities from already-liked titles once their genres are known."""
        if self._affinities or not self._liked:
            return
        from watchnext.common.constants import EVENT_WEIGHTS

        weight = EVENT_WEIGHTS["like"]
        for item_id in self._liked:
            for cat in item_categories.get(str(item_id), []) or []:
                prev = self._affinities.get(cat, 0.0)
                self._affinities[cat] = (1.0 - self.alpha) * prev + self.alpha * weight
        if self._affinities:
            self._clip_affinities()

    def apply(
        self,
        event: InteractionEvent,
        categories: list[str],
        as_of: datetime | None = None,
        now: datetime | None = None,
    ) -> UserFeatureState:
        weight = event.weight()
        rec = HistoryRecord(
            timestamp=_ts(event.timestamp),
            event_type=event.event_type,
            item_id=event.item_id,
            weight=weight,
            categories=list(categories),
        )
        if event.event_type != "impression":
            self.history.append(rec)
            if len(self.history) > self.history_cap:
                self.history = self.history[-self.history_cap :]
            self.interaction_count += 1
            self.engagement_sum += weight
            if event.item_id not in self._interacted_set:
                self._interacted_set.add(event.item_id)
                self._interacted.append(event.item_id)
            if event.event_type in POSITIVE_EVENT_TYPES:
                if event.item_id in self._disliked_set:
                    self._disliked_set.discard(event.item_id)
                    self._disliked = [i for i in self._disliked if i != event.item_id]
                if event.item_id not in self._liked_set:
                    self._liked_set.add(event.item_id)
                    self._liked.append(event.item_id)
            if event.event_type in NEGATIVE_EVENT_TYPES:
                if event.item_id in self._liked_set:
                    self._liked_set.discard(event.item_id)
                    self._liked = [i for i in self._liked if i != event.item_id]
                if event.item_id not in self._disliked_set:
                    self._disliked_set.add(event.item_id)
                    self._disliked.append(event.item_id)
            title = ""
            if event.metadata:
                title = str(event.metadata.get("title") or "")
            self._recent.append(
                {
                    "event_type": event.event_type,
                    "item_id": event.item_id,
                    "title": title,
                    "timestamp": rec.timestamp,
                }
            )
            if len(self._recent) > RECENT_ACTIONS_CAP:
                self._recent = self._recent[-RECENT_ACTIONS_CAP:]
            if abs(weight) > 0:
                a = self.alpha
                for cat in categories:
                    prev = self._affinities.get(cat, 0.0)
                    self._affinities[cat] = (1.0 - a) * prev + a * weight
                self._clip_affinities()

        clock = now or as_of or event.timestamp
        return self.snapshot(clock)

    def snapshot(self, as_of: datetime) -> UserFeatureState:
        as_of_ts = _ts(as_of)
        c24 = self._count_windows(as_of_ts, WINDOW_24H_SECONDS)
        c7 = self._count_windows(as_of_ts, WINDOW_7D_SECONDS)
        avg = self.engagement_sum / self.interaction_count if self.interaction_count else 0.0
        last = self.history[-1].timestamp if self.history else None
        return UserFeatureState(
            views_24h=c24["view"],
            likes_24h=c24["like"],
            skips_24h=c24["skip"],
            watches_24h=c24["watch"],
            views_7d=c7["view"],
            likes_7d=c7["like"],
            skips_7d=c7["skip"],
            watches_7d=c7["watch"],
            interaction_count=self.interaction_count,
            engagement_sum=round(self.engagement_sum, 6),
            avg_engagement=round(avg, 6),
            affinities={k: round(v, 6) for k, v in sorted(self._affinities.items())},
            last_activity_ts=last,
            feature_updated_at=as_of_ts,
            disliked_items=list(self._disliked),
            liked_items=list(self._liked),
            interacted_items=list(self._interacted),
            recent_actions=[dict(row) for row in self._recent],
        )

    def replay(
        self,
        events: Iterable[tuple[InteractionEvent, list[str]]],
        as_of: datetime | None = None,
    ) -> UserFeatureState:
        last: UserFeatureState | None = None
        for event, cats in events:
            last = self.apply(event, cats, as_of=event.timestamp)
        if last is None:
            return self.snapshot(as_of or datetime.now(UTC))
        if as_of is not None:
            return self.snapshot(as_of)
        return last

    def _clip_affinities(self) -> None:
        for k, v in list(self._affinities.items()):
            self._affinities[k] = max(-1.0, min(1.0, v))

    def _count_windows(self, as_of_ts: float, window: int) -> dict[str, int]:
        start = as_of_ts - window
        counts = {t: 0 for t in COUNT_EVENT_TYPES}
        for rec in self.history:
            if rec.timestamp < start or rec.timestamp > as_of_ts:
                continue
            if rec.event_type in counts:
                counts[rec.event_type] += 1
        return counts

    def export_history(self) -> list[dict[str, Any]]:
        return [
            {
                "timestamp": h.timestamp,
                "event_type": h.event_type,
                "item_id": h.item_id,
                "weight": h.weight,
                "categories": h.categories,
            }
            for h in self.history
        ]

    @classmethod
    def history_from_docs(cls, docs: list[dict[str, Any]]) -> list[HistoryRecord]:
        return [
            HistoryRecord(
                timestamp=float(d["timestamp"]),
                event_type=str(d["event_type"]),
                item_id=str(d["item_id"]),
                weight=float(d["weight"]),
                categories=list(d.get("categories") or []),
            )
            for d in docs
        ]
