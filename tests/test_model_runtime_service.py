"""Unit tests for ModelRuntimeService — u2 calls and repository are mocked."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from app.core.errors import ModelNotFoundError, SourceValidationError
from app.schemas.common import InlineDataSourceConfig
from app.schemas.forecast_models import (
    Forecast,
    ForecastedTimeValue,
    ForecastInput,
    ForecastSeries,
    ForecastTrainingInput,
    TimeParameters,
)
from app.schemas.models import CreateModelRequest
from app.schemas.tasks import ForecastRequest, TrainRequest
from app.services.metadata_service import MetadataService
from app.services.model_runtime_service import ModelRuntimeService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def metadata_svc(tmp_path: Path) -> MetadataService:
    svc = MetadataService(tmp_path / "metadata")
    (tmp_path / "metadata").mkdir()
    return svc


@pytest.fixture
def runtime(tmp_path: Path, metadata_svc: MetadataService) -> ModelRuntimeService:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return ModelRuntimeService(metadata_svc, models_dir, cache_dir=cache_dir)


def _make_forecast_result(_model_id: str, _version: str) -> Forecast:
    _start = datetime(2024, 1, 2, tzinfo=UTC)
    return Forecast(
        forecast_type="deterministic",
        forecast_date=datetime(2024, 1, 2, tzinfo=UTC),
        time_parameters=TimeParameters(timestep_minutes=60, horizon_hours=24),
        forecast_series=ForecastSeries(
            series_id="s1",
            variable_name="energy",
            values=[
                ForecastedTimeValue(
                    time=_start + timedelta(hours=h),
                    value=float(h),
                )
                for h in range(24)
            ],
        ),
    )


# ---------------------------------------------------------------------------
# train()
# ---------------------------------------------------------------------------


def test_train_calls_u2_train_and_records_version(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_training_input: ForecastTrainingInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    request = TrainRequest(forecast_training_input=minimal_training_input)

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    mock_repo = MagicMock()
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=mock_repo)
    mock_train = mocker.patch("app.services.model_runtime_service.u2_train")

    result = runtime.train("test-model", request)

    mock_train.assert_called_once()
    called_input: ForecastTrainingInput = mock_train.call_args[0][0]
    assert called_input.training_model_config.model_id == "test-model"
    assert called_input.training_model_config.model_version == "v1"

    mock_repo.save_model.assert_called_once_with("test-model", "v1", u2_dir)

    assert result["model_id"] == "test-model"
    assert result["version"] == "v1"
    assert "v1" in metadata_svc.get("test-model").versions


def test_train_autogenerates_version_when_missing(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_training_input: ForecastTrainingInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    no_version_input = minimal_training_input.model_copy(
        update={
            "training_model_config": minimal_training_input.training_model_config.model_copy(
                update={"model_version": None}
            )
        }
    )
    request = TrainRequest(forecast_training_input=no_version_input)

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=MagicMock())
    mocker.patch("app.services.model_runtime_service.u2_train")

    result = runtime.train("test-model", request)

    assert result["version"]
    assert result["version"] in metadata_svc.get("test-model").versions


def test_train_raises_when_no_source_provided(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    request = TrainRequest()
    with pytest.raises(ValueError, match="must provide"):
        runtime.train("test-model", request)


def test_train_parses_inline_data_source(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_training_input: ForecastTrainingInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    payload = minimal_training_input.model_dump(mode="json", by_alias=True)
    request = TrainRequest(data_source=InlineDataSourceConfig(type="inline", payload=payload))

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=MagicMock())
    mocker.patch("app.services.model_runtime_service.u2_train")

    result = runtime.train("test-model", request)
    assert result["model_id"] == "test-model"


def test_train_raises_source_validation_error_on_bad_payload(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    request = TrainRequest(
        data_source=InlineDataSourceConfig(type="inline", payload={"bad": "data"})
    )
    with pytest.raises(SourceValidationError):
        runtime.train("test-model", request)


def test_train_cleans_up_artifact_dir_after_save(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_training_input: ForecastTrainingInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    request = TrainRequest(forecast_training_input=minimal_training_input)

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    artifact = u2_dir / "test-model_v1"

    def _fake_train(_training_input: ForecastTrainingInput) -> None:
        artifact.mkdir()
        (artifact / "model.pkl").write_bytes(b"fake")

    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=MagicMock())
    mocker.patch("app.services.model_runtime_service.u2_train", side_effect=_fake_train)

    runtime.train("test-model", request)
    assert not artifact.exists()


# ---------------------------------------------------------------------------
# forecast()
# ---------------------------------------------------------------------------


def test_forecast_calls_u2_predict_and_returns_result(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_forecast_input: ForecastInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    metadata_svc.add_version("test-model", "v1")

    request = ForecastRequest(version="v1", forecast_input=minimal_forecast_input)
    mock_result = _make_forecast_result("test-model", "v1")

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=MagicMock())
    mock_predict = mocker.patch("app.services.model_runtime_service.u2_predict", return_value=mock_result)

    result = runtime.forecast("test-model", request)

    mock_predict.assert_called_once()
    called_input: ForecastInput = mock_predict.call_args[0][0]
    assert called_input.model_id == "test-model"
    assert called_input.model_version == "v1"
    assert result["forecast_type"] == "deterministic"


def test_forecast_loads_artifact_before_predict(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_forecast_input: ForecastInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    metadata_svc.add_version("test-model", "v1")

    request = ForecastRequest(version="v1", forecast_input=minimal_forecast_input)
    mock_result = _make_forecast_result("test-model", "v1")

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    mock_repo = MagicMock()
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=mock_repo)
    mocker.patch("app.services.model_runtime_service.u2_predict", return_value=mock_result)

    runtime.forecast("test-model", request)

    mock_repo.load_model.assert_called_once_with("test-model", "v1", u2_dir)


def test_forecast_resolves_latest_version(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_forecast_input: ForecastInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    metadata_svc.add_version("test-model", "v1")
    metadata_svc.add_version("test-model", "v2")

    request = ForecastRequest(version="latest", forecast_input=minimal_forecast_input)
    mock_result = _make_forecast_result("test-model", "v2")

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=MagicMock())
    mock_predict = mocker.patch("app.services.model_runtime_service.u2_predict", return_value=mock_result)

    runtime.forecast("test-model", request)

    called_input: ForecastInput = mock_predict.call_args[0][0]
    assert called_input.model_version == "v2"


def test_forecast_raises_when_no_trained_versions(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_forecast_input: ForecastInput,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    request = ForecastRequest(version="latest", forecast_input=minimal_forecast_input)
    with pytest.raises(ValueError, match="No trained versions"):
        runtime.forecast("test-model", request)


def test_forecast_raises_for_unknown_model(
    runtime: ModelRuntimeService,
    minimal_forecast_input: ForecastInput,
) -> None:
    request = ForecastRequest(version="latest", forecast_input=minimal_forecast_input)
    with pytest.raises(ModelNotFoundError):
        runtime.forecast("ghost", request)


def test_forecast_cleans_up_artifact_dir_after_predict(
    runtime: ModelRuntimeService,
    metadata_svc: MetadataService,
    minimal_forecast_input: ForecastInput,
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    metadata_svc.create(CreateModelRequest(model_id="test-model"))
    metadata_svc.add_version("test-model", "v1")

    request = ForecastRequest(version="v1", forecast_input=minimal_forecast_input)
    mock_result = _make_forecast_result("test-model", "v1")

    u2_dir = tmp_path / "u2"
    u2_dir.mkdir()
    artifact = u2_dir / "test-model_v1"

    def _fake_load(_model_id: str, _version: str, _target_dir: Path) -> Path:
        artifact.mkdir()
        (artifact / "model.pkl").write_bytes(b"fake")
        return artifact

    mock_repo = MagicMock()
    mock_repo.load_model.side_effect = _fake_load
    mocker.patch("app.services.model_runtime_service.U2_MODEL_DIR", new=u2_dir)
    mocker.patch("app.services.model_runtime_service.ModelRepositoryFactory.create", return_value=mock_repo)
    mocker.patch("app.services.model_runtime_service.u2_predict", return_value=mock_result)

    runtime.forecast("test-model", request)
    assert not artifact.exists()
