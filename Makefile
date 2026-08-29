PYTHON ?= python
GO ?= go

.PHONY: setup download-data prepare-data train evaluate up down test lint demo benchmark fmt

setup:
	$(PYTHON) -m pip install -e ".[dev]"
	$(GO) mod download

download-data:
	$(PYTHON) scripts/download_data.py

prepare-data:
	$(PYTHON) scripts/prepare_data.py

train:
	$(PYTHON) scripts/train.py

evaluate:
	$(PYTHON) scripts/evaluate.py

seed:
	$(PYTHON) scripts/seed_online_features.py

up:
	docker compose up -d --build

down:
	docker compose down

test:
	$(PYTHON) -m pytest -q
	$(GO) test ./...
	$(GO) test -race ./...

lint:
	$(PYTHON) -m ruff check watchnext services scripts tests benchmarks
	$(PYTHON) -m ruff format --check watchnext services scripts tests benchmarks
	$(PYTHON) -m mypy watchnext
	$(GO) vet ./...
	$(GO) fmt ./...

fmt:
	$(PYTHON) -m ruff format watchnext services scripts tests benchmarks
	$(GO) fmt ./...

demo:
	$(PYTHON) scripts/demo_realtime_personalization.py

benchmark:
	$(PYTHON) benchmarks/rec_load.py
	$(PYTHON) benchmarks/stream_load.py
