"""Optional local traffic generator for demos (not a production load test)."""

from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime
from urllib.request import Request, urlopen

API = "http://localhost:8080"


def send(user_id: str, item_id: str, event_type: str) -> None:
    payload = {
        "event_id": str(uuid.uuid4()),
        "schema_version": 1,
        "user_id": user_id,
        "item_id": item_id,
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    req = Request(
        f"{API}/v1/events",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=5) as resp:
        resp.read()


def main() -> None:
    rng = random.Random(0)
    types = ["view", "like", "skip", "watch"]
    for _ in range(20):
        send(str(rng.randint(1, 50)), str(rng.randint(1, 100)), rng.choice(types))
    print("sent 20 simulated events")


if __name__ == "__main__":
    main()
