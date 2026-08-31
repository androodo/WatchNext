# Public demo API: Go + Python ranker + Redis. UI is separate (Vercel).
FROM golang:1.24-bookworm AS gobuild
WORKDIR /src
COPY go.mod go.sum ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -o /recommendation-api ./cmd/recommendation-api

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends redis-server ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY deploy/render/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY watchnext ./watchnext
COPY services ./services
COPY --from=gobuild /recommendation-api /app/recommendation-api
COPY artifacts /app/artifacts
COPY data/processed/items.parquet /app/data/processed/items.parquet
COPY data/processed/item_categories.json /app/data/processed/item_categories.json
COPY data/processed/imdb_movies.parquet /app/data/processed/imdb_movies.parquet
COPY data/processed/imdb_movies.json /app/data/processed/imdb_movies.json
COPY deploy/render/start.sh /app/start.sh
RUN chmod +x /app/start.sh /app/recommendation-api

ENV PYTHONPATH=/app \
    WATCHNEXT_ROOT=/app \
    WATCHNEXT_ARTIFACTS=/app/artifacts \
    WATCHNEXT_PROCESSED=/app/data/processed \
    REDIS_URL=redis://127.0.0.1:6379/0 \
    ML_BASE_URL=http://127.0.0.1:8090 \
    INLINE_FEATURES=true \
    SHADOW_ENABLED=false \
    PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["/app/start.sh"]
