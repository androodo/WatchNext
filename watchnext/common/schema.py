"""Canonical interaction / event schema."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from watchnext.common.constants import EVENT_TYPES, EVENT_WEIGHTS, SCHEMA_VERSION


class InteractionEvent(BaseModel):
    event_id: str
    schema_version: int = SCHEMA_VERSION
    user_id: str
    item_id: str
    event_type: str
    timestamp: datetime
    value: float | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def _event_type(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type {v!r}")
        return v

    @field_validator("schema_version")
    @classmethod
    def _schema(cls, v: int) -> int:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {v}")
        return v

    @field_validator("user_id", "item_id", "event_id")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("field must be non-empty")
        return str(v)

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    def weight(self) -> float:
        if self.event_type == "rating":
            if self.value is None:
                return 0.0
            return (float(self.value) - 3.0) / 2.0
        return EVENT_WEIGHTS[self.event_type]


def new_event(
    user_id: str,
    item_id: str,
    event_type: str,
    timestamp: datetime | None = None,
    value: float | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> InteractionEvent:
    return InteractionEvent(
        event_id=event_id or str(uuid4()),
        user_id=str(user_id),
        item_id=str(item_id),
        event_type=event_type,
        timestamp=timestamp or datetime.now(UTC),
        value=value,
        request_id=request_id,
        metadata=metadata or {},
    )


def parse_event(payload: dict[str, Any]) -> InteractionEvent:
    return InteractionEvent.model_validate(payload)
