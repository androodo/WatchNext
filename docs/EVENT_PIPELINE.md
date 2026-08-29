# Event pipeline

Topics (that is the whole topology):

- `events.interactions` — user actions from `POST /v1/events`
- `events.impressions` — recommendation responses
- `events.dead-letter` — unparseable or invalid payloads

## Schema v1

Required: `event_id`, `schema_version`, `user_id`, `item_id`, `event_type`, `timestamp`.

Event types: `impression`, `view`, `like`, `skip`, `watch`, `dislike`, `rating`.

If Kafka publish fails, the API returns HTTP 503. It does not acknowledge an event that never hit the log.

## Delivery

Redpanda/Kafka gives **at-least-once** delivery. Consumers may see the same `event_id` twice.

Idempotency:

```
SET processed_event:{event_id} "1" NX EX 604800
```

If the key exists, skip the feature update.

Tradeoff: a crash after Redis feature write and before the SET would be unsafe if we SET last. We SET first, then update features. The opposite crash (SET succeeded, feature write failed) **drops** the event rather than double-counting. That is the chosen bias: over-counting affinities is worse for this demo than losing one event.

TTL of 7 days means a duplicate older than a week could apply again. Fine for local development; not a global exactly-once store.

## Consumer restart

Offsets are committed after processing. Restart resumes from the last commit. Combined with `event_id` dedupe, replays are safe within the TTL window.

## Poison messages

JSON failures and schema validation failures go to `events.dead-letter` with a reason. The consumer still commits so it does not stall.
