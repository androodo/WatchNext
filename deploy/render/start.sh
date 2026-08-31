#!/bin/bash
set -euo pipefail
cd /app

redis-server --daemonize yes --bind 127.0.0.1 --port 6379 --dir /tmp --dbfilename dump.rdb --save "" --appendonly no

python -m uvicorn services.ml_service.app:app --host 127.0.0.1 --port 8090 &
for _ in $(seq 1 90); do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/ready', timeout=2)" 2>/dev/null; then
    break
  fi
  sleep 2
done

exec ./recommendation-api
