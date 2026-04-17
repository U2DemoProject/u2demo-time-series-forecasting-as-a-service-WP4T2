"""Integration tests for the FastAPI routes using TestClient."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.forecast_models import (
    Forecast,
    ForecastedTimeValue,
    ForecastInput,
    ForecastSeries,
    ForecastTargetSeries,
    ForecastTrainingInput,
    TimeParameters,
    TimeValue,
)

# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------


def test_create_model(client: TestClient) -> None:
    resp = client.post("/api/v1/models", json={"model_id": "m1", "description": "my model"})
    assert resp.status_code == 201
    assert resp.json()["model_id"] == "m1"


def test_list_models_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/models")
    assert resp.status_code == 200
    assert resp.json()["models"] == []


def test_list_models_returns_created(client: TestClient) -> None:
    client.post("/api/v1/models", json={"model_id": "m1"})
    client.post("/api/v1/models", json={"model_id": "m2"})
    resp = client.get("/api/v1/models")
    ids = {m["model_id"] for m in resp.json()["models"]}
    assert ids == {"m1", "m2"}


def test_get_model_found(client: TestClient) -> None:
    client.post("/api/v1/models", json={"model_id": "m1"})
    resp = client.get("/api/v1/models/m1")
    assert resp.status_code == 200
    assert resp.json()["metadata"]["model_id"] == "m1"


def test_get_model_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/models/ghost")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Train endpoint
# ---------------------------------------------------------------------------


def test_train_model_sync(
    client: TestClient,
    minimal_training_input: ForecastTrainingInput,
) -> None:
    client.post("/api/v1/models", json={"model_id": "test-model"})
    payload = {
        "forecast_training_input": minimal_training_input.model_dump(
            mode="json", by_alias=True
        )
    }

    with patch("app.services.model_runtime_service.u2_train"):
        resp = client.post("/api/v1/models/test-model/train", json=payload)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["result"]["model_id"] == "test-model"


def test_train_model_missing_model_returns_422(client: TestClient) -> None:
    # model_id not registered — MetadataService.add_version will raise ModelNotFoundError
    with patch("app.services.model_runtime_service.u2_train"):
        resp = client.post(
            "/api/v1/models/unknown/train",
            json={
                "forecast_training_input": {
                    "forecast_type": "deterministic",
                    "time_parameters": {"timestep_minutes": 60, "horizon_hours": 24},
                    "model_config": {
                        "model_id": "unknown",
                        "model_version": "v1",
                    },
                    "target_series": {
                        "series_id": "s1",
                        "variable_name": "energy",
                        "training_values": [
                            {"time": "2024-01-01T00:00:00Z", "value": 0.0},
                            {"time": "2024-01-01T01:00:00Z", "value": 1.0},
                        ],
                    },
                }
            },
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Forecast endpoint
# ---------------------------------------------------------------------------

_FORECAST_START = datetime(2024, 1, 2, tzinfo=UTC)
_MOCK_FORECAST = Forecast(
    forecast_type="deterministic",
    forecast_date=datetime(2024, 1, 2, tzinfo=UTC),
    time_parameters=TimeParameters(timestep_minutes=60, horizon_hours=24),
    forecast_series=ForecastSeries(
        series_id="s1",
        variable_name="energy",
        values=[
            ForecastedTimeValue(
                time=_FORECAST_START + timedelta(hours=h),
                value=float(h),
            )
            for h in range(24)
        ],
    ),
)


def test_forecast_model_sync(
    client: TestClient,
    minimal_training_input: ForecastTrainingInput,
) -> None:
    client.post("/api/v1/models", json={"model_id": "test-model"})

    # First train so a version exists.
    with patch("app.services.model_runtime_service.u2_train"):
        client.post(
            "/api/v1/models/test-model/train",
            json={
                "forecast_training_input": minimal_training_input.model_dump(
                    mode="json", by_alias=True
                )
            },
        )

    _hist_start = datetime(2024, 1, 1, tzinfo=UTC)
    hist = [
        TimeValue(time=_hist_start + timedelta(hours=h), value=float(h))
        for h in range(48)
    ]
    forecast_input = ForecastInput(
        forecast_type="deterministic",
        time_parameters=TimeParameters(timestep_minutes=60, horizon_hours=24),
        target_series=ForecastTargetSeries(
            series_id="s1", variable_name="energy", historical_values=hist
        ),
    )

    with patch(
        "app.services.model_runtime_service.u2_predict", return_value=_MOCK_FORECAST
    ):
        resp = client.post(
            "/api/v1/models/test-model/forecast",
            json={"forecast_input": forecast_input.model_dump(mode="json")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["result"]["forecast_type"] == "deterministic"
    assert len(body["result"]["forecast_series"]["values"]) == 24


def test_forecast_no_versions_returns_422(client: TestClient) -> None:
    client.post("/api/v1/models", json={"model_id": "m1"})
    _h_start = datetime(2024, 1, 1, tzinfo=UTC)
    hist = [
        TimeValue(time=_h_start + timedelta(hours=h), value=float(h))
        for h in range(2)
    ]
    forecast_input = ForecastInput(
        forecast_type="deterministic",
        time_parameters=TimeParameters(timestep_minutes=60, horizon_hours=24),
        target_series=ForecastTargetSeries(
            series_id="s1", variable_name="energy", historical_values=hist
        ),
    )
    resp = client.post(
        "/api/v1/models/m1/forecast",
        json={"forecast_input": forecast_input.model_dump(mode="json")},
    )
    assert resp.status_code == 422
