import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from u2demo_time_series_forecasting.predict import predict as u2_predict
from u2demo_time_series_forecasting.train import train as u2_train

from app.core.errors import SourceValidationError
from app.factories.data_source_factory import DataSourceFactory
from app.schemas.forecast_models import Forecast, ForecastInput, ForecastTrainingInput
from app.schemas.tasks import ForecastRequest, TrainRequest
from app.services.metadata_service import MetadataService


class ModelRuntimeService:
    """Coordinates training and forecasting via the u2 core library."""

    def __init__(self, metadata_service: MetadataService, models_dir: Path) -> None:
        self.metadata_service = metadata_service
        self.models_dir = models_dir
        # u2 reads MODEL_PATH from the environment; keep it in sync with our config.
        os.environ["MODEL_PATH"] = str(models_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_training_input(self, request: TrainRequest) -> ForecastTrainingInput:
        """Return a ForecastTrainingInput from the request, validating the source."""
        if request.forecast_training_input is not None:
            return request.forecast_training_input

        if request.data_source is not None:
            source = DataSourceFactory.create(request.data_source)
            payload = source.fetch(request.data_source)
            try:
                return ForecastTrainingInput.model_validate(payload)
            except Exception as exc:
                raise SourceValidationError(
                    f"data_source payload is not a valid ForecastTrainingInput: {exc}"
                ) from exc

        raise ValueError(
            "TrainRequest must provide either 'forecast_training_input' or 'data_source'."
        )

    def _resolve_forecast_input(self, request: ForecastRequest) -> ForecastInput:
        """Return a ForecastInput from the request, validating the source."""
        if request.forecast_input is not None:
            return request.forecast_input

        if request.data_source is not None:
            source = DataSourceFactory.create(request.data_source)
            payload = source.fetch(request.data_source)
            try:
                return ForecastInput.model_validate(payload)
            except Exception as exc:
                raise SourceValidationError(
                    f"data_source payload is not a valid ForecastInput: {exc}"
                ) from exc

        raise ValueError(
            "ForecastRequest must provide either 'forecast_input' or 'data_source'."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, model_id: str, request: TrainRequest) -> dict[str, Any]:
        """Train a model using the u2 core library and record the version."""
        training_input = self._resolve_training_input(request)

        # Derive the version; auto-generate a UTC timestamp if not set.
        version: str | None = training_input.training_model_config.model_version
        if not version:
            version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

        # Ensure the model_id and version in the payload match TSFaaS routing.
        updated_config = training_input.training_model_config.model_copy(
            update={"model_id": model_id, "model_version": version}
        )
        training_input = training_input.model_copy(
            update={"training_model_config": updated_config}
        )

        u2_train(training_input)

        self.metadata_service.add_version(model_id, version)
        return {"model_id": model_id, "version": version}

    def forecast(self, model_id: str, request: ForecastRequest) -> dict[str, Any]:
        """Run inference using the u2 core library and return the Forecast payload."""
        metadata = self.metadata_service.get(model_id)

        version = request.version
        if version == "latest":
            if not metadata.versions:
                raise ValueError(f"No trained versions available for model '{model_id}'.")
            version = metadata.versions[-1]

        forecast_input = self._resolve_forecast_input(request)

        # Ensure model_id/model_version point to the correct artifact.
        forecast_input = forecast_input.model_copy(
            update={"model_id": model_id, "model_version": version}
        )

        result: Forecast = u2_predict(forecast_input)
        return result.model_dump(mode="json")
