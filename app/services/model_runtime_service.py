import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from u2demo_time_series_forecasting.constants.paths import MODEL_DIR as U2_MODEL_DIR
from u2demo_time_series_forecasting.data_models_v2 import forecast_to_v2
from u2demo_time_series_forecasting.predict import predict as u2_predict
from u2demo_time_series_forecasting.train import train as u2_train
from u2demo_time_series_forecasting.versioning import parse_forecast_payload, parse_training_payload

from app.core.errors import SourceValidationError
from app.factories.data_source_factory import DataSourceFactory
from app.factories.model_repository_factory import ModelRepositoryFactory
from app.schemas.common import VolumeModelSourceConfig
from app.schemas.forecast_models import (
    Forecast,
    ForecastInput,
    ForecastInputV2,
    ForecastTrainingInput,
    ForecastTrainingInputV2,
)
from app.schemas.tasks import ForecastRequest, TrainRequest
from app.services.metadata_service import MetadataService

# BLOCKER: u2demo_time_series_forecasting reads MODEL_DIR from constants/paths.py at
# **module import time** as `BASEDIR / "models"` (where BASEDIR is derived from __file__).
# It does NOT read os.environ["MODEL_PATH"] at all — the env-var override attempted in
# earlier versions of this service was silently a no-op. Per-call os.environ["MODEL_PATH"]
# assignment has the same problem. Until the upstream library exposes a runtime setter or
# respects an env-var at call time, the only correct approach is to use U2_MODEL_DIR as
# the artifact landing zone and move artifacts in/out around each call.


class ModelRuntimeService:
    """Coordinates training and forecasting via the u2 core library."""

    def __init__(self, metadata_service: MetadataService, models_dir: Path, cache_dir: Path) -> None:
        self.metadata_service = metadata_service
        self.models_dir = models_dir
        self.cache_dir = cache_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_training_input(self, request: TrainRequest) -> ForecastTrainingInput | ForecastTrainingInputV2:
        if request.forecast_training_input is not None:
            return request.forecast_training_input

        if request.data_source is not None:
            source = DataSourceFactory.create(request.data_source)
            payload = source.fetch(request.data_source)
            try:
                return parse_training_payload(payload)
            except Exception as exc:
                raise SourceValidationError(
                    f"data_source payload is not a valid v1 or v2 training input: {exc}"
                ) from exc

        raise ValueError(
            "TrainRequest must provide either 'forecast_training_input' or 'data_source'."
        )

    def _resolve_forecast_input(self, request: ForecastRequest) -> ForecastInput | ForecastInputV2:
        if request.forecast_input is not None:
            return request.forecast_input

        if request.data_source is not None:
            source = DataSourceFactory.create(request.data_source)
            payload = source.fetch(request.data_source)
            try:
                return parse_forecast_payload(payload)
            except Exception as exc:
                raise SourceValidationError(
                    f"data_source payload is not a valid v1 or v2 forecast input: {exc}"
                ) from exc

        raise ValueError(
            "ForecastRequest must provide either 'forecast_input' or 'data_source'."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, model_id: str, request: TrainRequest) -> dict[str, Any]:
        """Train a model and persist the artifact via the repository."""
        training_input = self._resolve_training_input(request)
        # v2 requests are trained through their v1 equivalent, as the library's train_v2 does
        if isinstance(training_input, ForecastTrainingInputV2):
            training_input = training_input.to_v1()

        version: str | None = training_input.training_model_config.model_version
        if not version:
            version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

        updated_config = training_input.training_model_config.model_copy(
            update={"model_id": model_id, "model_version": version}
        )
        training_input = training_input.model_copy(
            update={"training_model_config": updated_config}
        )

        source_config = request.model_source or VolumeModelSourceConfig()
        repository = ModelRepositoryFactory.create(source_config, self.models_dir, self.cache_dir)

        artifact_name = f"{model_id}_{version}"
        artifact_path = U2_MODEL_DIR / artifact_name
        try:
            U2_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            u2_train(training_input)
            repository.save_model(model_id, version, U2_MODEL_DIR)
        finally:
            if artifact_path.exists():
                shutil.rmtree(artifact_path)

        self.metadata_service.add_version(model_id, version)
        return {"model_id": model_id, "version": version}

    def forecast(self, model_id: str, request: ForecastRequest) -> dict[str, Any]:
        """Load a model artifact and run inference via the u2 core library."""
        metadata = self.metadata_service.get(model_id)

        version = request.version
        if version == "latest":
            if not metadata.versions:
                raise ValueError(f"No trained versions available for model '{model_id}'.")
            version = metadata.versions[-1]

        forecast_input = self._resolve_forecast_input(request)
        forecast_input = forecast_input.model_copy(
            update={"model_id": model_id, "model_version": version}
        )

        source_config = request.model_source or VolumeModelSourceConfig()
        repository = ModelRepositoryFactory.create(source_config, self.models_dir, self.cache_dir)

        artifact_name = f"{model_id}_{version}"
        artifact_path = U2_MODEL_DIR / artifact_name
        try:
            U2_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            repository.load_model(model_id, version, U2_MODEL_DIR)
            # v2 requests are forecast through their v1 equivalent, as the library's predict_v2 does
            is_v2 = isinstance(forecast_input, ForecastInputV2)
            result: Forecast = u2_predict(forecast_input.to_v1() if is_v2 else forecast_input)
        finally:
            if artifact_path.exists():
                shutil.rmtree(artifact_path)

        if isinstance(forecast_input, ForecastInputV2):
            return forecast_to_v2(result, forecast_input).model_dump(mode="json")
        return result.model_dump(mode="json")
