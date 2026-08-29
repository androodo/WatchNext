#!/usr/bin/env python
"""DEMO 5: stop ranker (ML rank path), confirm API still serves with fallback_used."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "http://localhost:8080"


def get(path: str) -> tuple[int, dict]:
    req = urllib.request.Request(API + path)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body}


def compose(*args: str) -> None:
    cmd = ["docker", "compose", *args]
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else "42"
    print("1. request with full stack")
    code, before = get(f"/v1/recommendations/{user}?limit=5")
    print(
        "   status",
        code,
        "fallback",
        before.get("fallback_used"),
        "model",
        before.get("model_version"),
    )

    print("2. stop ml-service (ranker + candidates)")
    compose("stop", "ml-service")
    time.sleep(2)

    print("3. request while ML is down")
    code, down = get(f"/v1/recommendations/{user}?limit=5")
    print(
        "   status",
        code,
        "fallback",
        down.get("fallback_used"),
        "reason",
        down.get("fallback_reason"),
    )
    if code != 200:
        print("   WARNING: expected HTTP 200 degraded response")
    if not down.get("fallback_used"):
        print("   WARNING: expected fallback_used=true")

    print("4. start ml-service")
    compose("start", "ml-service")
    for _ in range(30):
        try:
            urllib.request.urlopen("http://localhost:8090/health", timeout=2)
            break
        except Exception:
            time.sleep(1)

    print("5. request after restart")
    code, after = get(f"/v1/recommendations/{user}?limit=5")
    print(
        "   status",
        code,
        "fallback",
        after.get("fallback_used"),
        "model",
        after.get("model_version"),
    )

    report = {
        "before": {
            "status": code,
            **{k: before.get(k) for k in ("fallback_used", "fallback_reason", "model_version")},
        },
        "ml_down": {
            "fallback_used": down.get("fallback_used"),
            "fallback_reason": down.get("fallback_reason"),
        },
        "after": {
            "fallback_used": after.get("fallback_used"),
            "model_version": after.get("model_version"),
        },
    }
    (ROOT / "reports" / "demo_failure.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if os.environ.get("SKIP_COMPOSE") == "1":
        print("SKIP_COMPOSE=1; not stopping containers")
        sys.exit(0)
    main()
