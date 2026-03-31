from datetime import datetime, timezone
from typing import Any

from app.factories.data_source_factory import DataSourceFactory
from app.factories.model_repository_factory import ModelRepositoryFactory
from app.schemas.tasks import ForecastRequest, TrainRequest
from app.services.metadata_service import MetadataService


class ModelRuntimeService:
    def __init__(self, metadata_service: MetadataService, models_dir, cache_dir) -> None:
        self.metadata_service = metadata_service
        self.models_dir = models_dir
        self.cache_dir = cache_dir

    def train(self, model_id: str, request: TrainRequest) -> dict[str, Any]:
        data_source = DataSourceFactory.create(request.data_source)
        dataset = data_source.fetch(request.data_source.model_dump().get("payload") or request.data_source.model_dump().get("request", {}))

        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        repository = ModelRepositoryFactory.create(request.model_source, self.models_dir, self.cache_dir)

        # Placeholder artifact until forecasting backend is integrated.
        artifact = {
            "model_id": model_id,
            "version": version,
            "trained_with": "placeholder-backend",
            "hyperparameters": request.hyperparameters,
            "dataset_preview_keys": list(dataset.keys()) if isinstance(dataset, dict) else [],
        }
        repository.save_model(model_id=model_id, version=version, payload=artifact)
        self.metadata_service.add_version(model_id, version)
        return {"model_id": model_id, "version": version}

    def forecast(self, model_id: str, request: ForecastRequest) -> dict[str, Any]:
        metadata = self.metadata_service.get(model_id)
        version = request.version
        if version == "latest":
            if not metadata.versions:
                raise ValueError("No trained versions available for this model")
            version = metadata.versions[-1]

        data_source = DataSourceFactory.create(request.data_source)
        dataset = data_source.fetch(request.data_source.model_dump().get("payload") or request.data_source.model_dump().get("request", {}))
        repository = ModelRepositoryFactory.create(request.model_source, self.models_dir, self.cache_dir)
        artifact = repository.load_model(model_id=model_id, version=version)

        # Placeholder prediction payload until forecasting backend is integrated.
        predictions = [
            {
                "step": i + 1,
                "value": None,
                "note": "Forecast backend not yet integrated",
            }
            for i in range(request.horizon)
        ]

        return {
            "model_id": model_id,
            "version": artifact.get("version", version),
            "horizon": request.horizon,
            "predictions": predictions,
            "input_keys": list(dataset.keys()) if isinstance(dataset, dict) else [],
        }
