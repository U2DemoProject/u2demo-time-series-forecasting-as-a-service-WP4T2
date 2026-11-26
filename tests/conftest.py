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


_TV_V2 = [{"timestamp": tv.time.isoformat(), "value": tv.value} for tv in _TV]
_TARGET_V2 = {
    "series_id": "s1",
    "observedProperty": "ActivePower",
    "hasFeatureOfInterest": "load_1",
    "unit_symbol": "kW",
}


@pytest.fixture
def minimal_training_payload_v2() -> dict:
    """Minimal v2 training payload (U2Demo data models v2)."""
    return {
        "hasTimeParameters": {"timestep_minutes": 60, "horizon_hours": 24},
        "hasUserForecastPreferences": {
            "forecast_type": "DETERMINISTIC",
            "model_id": "test-model",
            "model_preset": "fast_training",
            "model_version": "v1",
        },
        "target_series": {**_TARGET_V2, "training_values": _TV_V2},
    }


@pytest.fixture
def minimal_forecast_payload_v2() -> dict:
    """Minimal v2 forecast payload (U2Demo data models v2)."""
    return {
        "forecastId": "forecast-1",
        "forecast_type": "DETERMINISTIC",
        "hasTimeParameters": {"timestep_minutes": 60, "horizon_hours": 24},
        "model_id": "test-model",
        "model_version": "v1",
        "target_series": {**_TARGET_V2, "historical_values": _TV_V2},
    }


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

    # Clear the lru_cache so the patched env vars take effect.
    from app.core.config import get_settings
    from app.jobs.service import get_job_backend

    get_settings.cache_clear()
    get_job_backend.cache_clear()

    from app.main import app

    return TestClient(app)
