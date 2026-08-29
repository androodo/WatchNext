"""Redpanda consumer: validate → dedupe → update Redis → dead-letter on poison."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from prometheus_client import Counter, Histogram, start_http_server
from redis import Redis

from pulserank_ml.online.processor import FeatureProcessor

log = structlog.get_logger("feature_consumer")

EVENTS_PROCESSED = Counter("pulserank_events_processed_total", "Events processed", ["status"])
INVALID = Counter("pulserank_invalid_events_total", "Invalid events")
DUPES = Counter("pulserank_duplicate_events_total", "Duplicate event ids")
FRESHNESS = Histogram(
    "pulserank_feature_freshness_seconds",
    "event timestamp to feature update",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

ROOT = Path(os.environ.get("PULSERANK_ROOT", Path(__file__).resolve().parents[2]))
CAT_PATH = Path(os.environ.get("PULSERANK_ITEM_CATEGORIES", ROOT / "data" / "processed" / "item_categories.json"))


def load_categories() -> dict[str, list[str]]:
    if not CAT_PATH.exists():
        log.warning("item_categories_missing", path=str(CAT_PATH))
        return {}
    return json.loads(CAT_PATH.read_text(encoding="utf-8"))


async def consume() -> None:
    brokers = os.environ.get("KAFKA_BROKERS", "localhost:19092")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    topic = os.environ.get("INTERACTIONS_TOPIC", "events.interactions")
    dlq = os.environ.get("DLQ_TOPIC", "events.dead-letter")
    group = os.environ.get("CONSUMER_GROUP", "pulserank-features")
    metrics_port = int(os.environ.get("METRICS_PORT", "8091"))

    start_http_server(metrics_port)
    categories = load_categories()
    r = Redis.from_url(redis_url, decode_responses=True)
    processor = FeatureProcessor(r, categories)  # sync client: get/set match RedisLike

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=brokers,
        group_id=group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda b: b,
    )
    producer = AIOKafkaProducer(bootstrap_servers=brokers)
    await consumer.start()
    await producer.start()
    log.info("consumer_started", brokers=brokers, topic=topic)
    try:
        async for msg in consumer:
            started = time.time()
            try:
                payload = json.loads(msg.value.decode("utf-8"))
            except Exception as exc:
                INVALID.inc()
                EVENTS_PROCESSED.labels(status="invalid").inc()
                await producer.send_and_wait(
                    dlq,
                    json.dumps({"reason": f"json:{exc}", "raw": msg.value.decode("utf-8", "replace")}).encode(),
                )
                await consumer.commit()
                continue
            result = processor.process_payload(payload)
            if result.status == "invalid":
                INVALID.inc()
                EVENTS_PROCESSED.labels(status="invalid").inc()
                await producer.send_and_wait(
                    dlq,
                    json.dumps({"reason": result.reason, "payload": payload}).encode(),
                )
            elif result.status == "duplicate":
                DUPES.inc()
                EVENTS_PROCESSED.labels(status="duplicate").inc()
                log.info("duplicate_event", event_id=result.event_id, user_id=result.user_id)
            else:
                EVENTS_PROCESSED.labels(status="applied").inc()
                ts = payload.get("timestamp")
                try:
                    from datetime import datetime

                    event_ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
                    FRESHNESS.observe(max(0.0, time.time() - event_ts))
                except Exception:
                    pass
                log.info(
                    "event_applied",
                    event_id=result.event_id,
                    user_id=result.user_id,
                    latency_ms=round((time.time() - started) * 1000, 2),
                )
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
        r.close()


def main() -> None:
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    asyncio.run(consume())


if __name__ == "__main__":
    main()
