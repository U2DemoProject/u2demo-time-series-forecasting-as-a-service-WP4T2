from app.core.config import get_settings
from app.schemas.tasks import ForecastRequest, TrainRequest
from app.services.metadata_service import MetadataService
from app.services.model_runtime_service import ModelRuntimeService


def _runtime() -> ModelRuntimeService:
    settings = get_settings()
    metadata_service = MetadataService(settings.metadata_dir)
    return ModelRuntimeService(metadata_service, settings.models_dir)


def train_task(payload: dict) -> dict:
    """Run training task payload inside the worker process."""
    request = TrainRequest.model_validate(payload["request"])
    model_id = payload["model_id"]
    runtime = _runtime()
    return runtime.train(model_id=model_id, request=request)


def forecast_task(payload: dict) -> dict:
    """Run forecasting task payload inside the worker process."""
    request = ForecastRequest.model_validate(payload["request"])
    model_id = payload["model_id"]
    runtime = _runtime()
    return runtime.forecast(model_id=model_id, request=request)
