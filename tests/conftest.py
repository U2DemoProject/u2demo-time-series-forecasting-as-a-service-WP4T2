"""Shared fixtures for the TSFaaS test suite."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schemas.forecast_models import (
    ForecastInput,
    ForecastTargetSeries,
    ForecastTrainingInput,
    ModelConfig,
    TimeParameters,
    TimeValue,
    TrainingTargetSeries,
)

# ---------------------------------------------------------------------------
# Storage fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path: Path) -> dict[str, Path]:
    """Return a dict of temporary storage directories."""
    dirs = {
        "models": tmp_path / "models",
        "metadata": tmp_path / "metadata",
        "cache": tmp_path / "cache",
    }
    for d in dirs.values():
        d.mkdir()
    return dirs


# ---------------------------------------------------------------------------
# Schema fixtures — minimal valid payloads
# ---------------------------------------------------------------------------

_START = datetime(2024, 1, 1, tzinfo=UTC)
_TV = [
    TimeValue(time=_START + timedelta(hours=h), value=float(h))
    for h in range(48)
]


@pytest.fixture
def minimal_training_input() -> ForecastTrainingInput:
    return ForecastTrainingInput(
        forecast_type="deterministic",
        time_parameters=TimeParameters(timestep_minutes=60, horizon_hours=24),
        model_config=ModelConfig(
                model_id="test-model",
                model_preset="fast_training",
                model_version="v1",
            ),
        target_series=TrainingTargetSeries(
            series_id="s1",
            variable_name="energy",
            training_values=_TV,
        ),
    )


@pytest.fixture
def minimal_forecast_input() -> ForecastInput:
    return ForecastInput(
        forecast_type="deterministic",
        time_parameters=TimeParameters(timestep_minutes=60, horizon_hours=24),
        model_id="test-model",
        model_version="v1",
        target_series=ForecastTargetSeries(
            series_id="s1",
            variable_name="energy",
            historical_values=_TV,
        ),
    )


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------


@pytest.fixture
def client(storage: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient with JOBS_BACKEND=memory and isolated storage."""
    # Patch settings so the app uses tmp dirs and the in-memory job backend.
    monkeypatch.setenv("JOBS_BACKEND", "memory")
    monkeypatch.setenv("MODELS_DIR", str(storage["models"]))
    monkeypatch.setenv("METADATA_DIR", str(storage["metadata"]))
    monkeypatch.setenv("CACHE_DIR", str(storage["cache"]))
    monkeypatch.setenv("MODEL_PATH", str(storage["models"]))

    # Clear the lru_cache so the patched env vars take effect.
    from app.core.config import get_settings
    from app.jobs.service import get_job_backend

    get_settings.cache_clear()
    get_job_backend.cache_clear()

    from app.main import app

    return TestClient(app)
