# Time Series Tool as a Service - Skeleton

Base skeleton for a Linux-first model service with:
- multiple model identifiers (`model_id`)
- pluggable data source factory (`inline` and `url`)
- pluggable model repository factory (`volume` default and `url`)
- API + worker split using Docker Compose

The forecasting backend and concrete data model are intentionally placeholder stubs.

## Quick Start

### Option A: Docker Compose
```bash
docker compose up --build
```

API docs:
- http://localhost:8001/docs

Override host port if needed:
```bash
API_HOST_PORT=8010 docker compose up --build
```

### Option B: Local run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Option C: Poetry run
```bash
poetry install --with dev
poetry run uvicorn app.main:app --reload
```

Tooling checks:
```bash
poetry run ruff check .
poetry run ruff format .
poetry run pyright app worker.py
```

## Main Endpoints
- POST `/api/v1/models`
- GET `/api/v1/models/{model_id}`
- POST `/api/v1/models/{model_id}/train`
- POST `/api/v1/models/{model_id}/forecast`
- GET `/api/v1/jobs/{job_id}`

## Notes
- Default `JOBS_BACKEND=redis`, so compose starts `api`, `worker`, and `redis`.
- For synchronous local behavior, set `JOBS_BACKEND=memory`.
- Default API host port is `8001` to avoid collisions with common local development servers.
- Model artifacts are currently JSON placeholders under `storage/models`.
