<div align="center"><img src="doc/U2DEMO_logo.png" alt="U2Demo Logo" width="200px" /></div>

# TSFaaS — U2Demo Time Series Forecasting as a Service

This document has been produced in the context of the U2Demo project. Views and opinions expressed in this document are
however those of the authors only and do not necessarily reflect those of the European Union or the European Climate,
Infrastructure and Environment Executive Agency (CINEA). Neither the European Union nor the granting authority can be
held responsible for them. U2Demo has received funding from the European Union's Horizon Europe programme under grant
agreement no. 101160684.

This repository provides a reference implementation of an HTTP service built on top of the
[U2 Time Series Prediction](https://git.eifer.kit.edu/dev-team/u2-demo/u2-time-series-prediction-final) core library.
It demonstrates how to wrap the forecasting engine behind a REST API with asynchronous job processing, making it easy
to integrate time-series training and inference into larger systems.

The service is built with **FastAPI**, uses **Redis + RQ** for async job execution, and packages everything via
**Docker Compose** so that a single command brings up the full stack (API, worker, Redis).

## Architecture

This repo is the API and orchestration layer; the forecasting brain is the
[`u2`](https://git.eifer.kit.edu/dev-team/u2-demo/u2-time-series-prediction-final) library, pulled in as a dependency.
Three processes cooperate at runtime:

- **`app/main.py`** — FastAPI application exposing the REST endpoints and enqueuing jobs.
- **`worker.py`** — RQ worker that consumes the `tsfaas` queue and invokes `u2` for training/forecasting.
- **Redis** — job queue and result store shared by the API and the worker.

## Documentation

- [Workflow Explanation](doc/workflow-explanation.md) — architecture overview and request lifecycle.
- [Household Forecast Example (Jupyter Notebook)](doc/example_household_forecast.ipynb) — end-to-end walkthrough: generate synthetic data, train a model, and produce a 24h forecast via the API.

## Prerequisites

- Python `>=3.12,<3.13`
- [Poetry](https://python-poetry.org/) `>=2.0` (recommended) or `pip`
- Docker and Docker Compose — required for Option A, optional otherwise
- Redis — required when `JOBS_BACKEND=redis` (the default); not needed with `JOBS_BACKEND=memory`

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

### Option B: Local run (pip)

Requires a running Redis on `REDIS_URL` (default `redis://localhost:6379/0`) unless you set `JOBS_BACKEND=memory`
for synchronous, in-process execution.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Option B.1: synchronous, no Redis needed
JOBS_BACKEND=memory uvicorn app.main:app --reload

# Option B.2: async mode — start the worker in a second terminal
uvicorn app.main:app --reload
python worker.py
```

### Option C: Poetry

Same Redis / `JOBS_BACKEND` requirement as Option B.

```bash
poetry install --with dev

# synchronous
JOBS_BACKEND=memory poetry run uvicorn app.main:app --reload

# async (second terminal: poetry run python worker.py)
poetry run uvicorn app.main:app --reload
```

## Main Endpoints

Interactive, schema-accurate docs are available at [`/docs`](http://localhost:8001/docs) (Swagger UI) and
[`/redoc`](http://localhost:8001/redoc) once the service is running — refer to those for request/response shapes.

- `POST /api/v1/models` — register a new model
- `GET  /api/v1/models` — list registered models
- `GET  /api/v1/models/{model_id}` — get model metadata and versions
- `POST /api/v1/models/{model_id}/train` — submit a training job
- `POST /api/v1/models/{model_id}/forecast` — submit a forecast job
- `GET  /api/v1/jobs/{job_id}` — poll job status / retrieve results

## Configuration

All settings are read from environment variables (or a `.env` file). Defaults are suitable for local development.

| Variable              | Default                        | Description                                                                 |
| --------------------- | ------------------------------ | --------------------------------------------------------------------------- |
| `APP_NAME`            | `tsfaas`                       | Application name reported by FastAPI.                                       |
| `APP_ENV`             | `dev`                          | Deployment environment tag.                                                 |
| `API_PREFIX`          | `/api/v1`                      | URL prefix for all API routes.                                              |
| `API_HOST_PORT`       | `8001`                         | Host port published by Docker Compose.                                      |
| `JOBS_BACKEND`        | `redis`                        | Job execution backend: `redis` (async via RQ) or `memory` (synchronous).    |
| `REDIS_URL`           | `redis://localhost:6379/0`     | Redis connection URL; used when `JOBS_BACKEND=redis`.                       |
| `MODELS_DIR`          | `storage/models`               | Where trained model artifacts are persisted.                                |
| `METADATA_DIR`        | `storage/metadata`             | Where model metadata is persisted.                                          |
| `CACHE_DIR`           | `storage/cache`                | Working cache directory.                                                    |
| `ALLOWED_DATA_HOSTS`  | `*`                            | Comma-separated allow-list for external data source hosts (`*` = any).      |
| `ALLOWED_MODEL_HOSTS` | `*`                            | Comma-separated allow-list for external model source hosts (`*` = any).    |

## Testing

```bash
poetry install --with dev
poetry run pytest
```

Tooling checks:

```bash
poetry run ruff check .
poetry run ruff format .
poetry run pyright app worker.py
```
