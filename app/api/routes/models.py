from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.core.errors import ModelNotFoundError, SourceValidationError
from app.jobs.service import get_job_backend
from app.schemas.models import CreateModelRequest, ModelInfoResponse, ModelListResponse
from app.schemas.tasks import ForecastRequest, TrainRequest
from app.services.metadata_service import MetadataService
from app.services.model_runtime_service import ModelRuntimeService

router = APIRouter()


@router.post("/models", status_code=201)
def create_model(request: CreateModelRequest) -> dict:
    """Create persisted metadata for a new model id."""
    settings = get_settings()
    metadata_service = MetadataService(settings.metadata_dir)
    metadata_service.create(request)
    return {"model_id": request.model_id, "status": "created"}


@router.get("/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    """List all registered model metadata records."""
    settings = get_settings()
    metadata_service = MetadataService(settings.metadata_dir)
    return ModelListResponse(models=metadata_service.list_models())


@router.get("/models/{model_id}", response_model=ModelInfoResponse)
def get_model(model_id: str) -> ModelInfoResponse:
    """Return metadata for a single model id."""
    settings = get_settings()
    metadata_service = MetadataService(settings.metadata_dir)
    try:
        metadata = metadata_service.get(model_id)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ModelInfoResponse(metadata=metadata)


@router.post("/models/{model_id}/train", status_code=202)
def train_model(model_id: str, request: TrainRequest) -> dict:
    """Queue or run training for a model, depending on backend mode."""
    settings = get_settings()

    if settings.jobs_backend == "memory":
        metadata_service = MetadataService(settings.metadata_dir)
        runtime = ModelRuntimeService(metadata_service, settings.models_dir, settings.cache_dir)
        try:
            result = runtime.train(model_id=model_id, request=request)
            return {"job_id": "sync", "status": "succeeded", "result": result}
        except (ModelNotFoundError, SourceValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_backend = get_job_backend()
    payload = {
        "model_id": model_id,
        "request": request.model_dump(mode="json"),
        "submitted_at": datetime.now(UTC).isoformat(),
    }
    job_id = job_backend.enqueue(task_name="train", payload=payload)
    return {"job_id": job_id, "model_id": model_id, "status": "queued"}


@router.post("/models/{model_id}/forecast", status_code=202)
def forecast_model(model_id: str, request: ForecastRequest) -> dict:
    """Queue or run forecasting for a model, depending on backend mode."""
    settings = get_settings()

    if settings.jobs_backend == "memory":
        metadata_service = MetadataService(settings.metadata_dir)
        runtime = ModelRuntimeService(metadata_service, settings.models_dir, settings.cache_dir)
        try:
            result = runtime.forecast(model_id=model_id, request=request)
            return {"job_id": "sync", "status": "succeeded", "result": result}
        except (ModelNotFoundError, SourceValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    job_backend = get_job_backend()
    payload = {
        "model_id": model_id,
        "request": request.model_dump(mode="json"),
        "submitted_at": datetime.now(UTC).isoformat(),
    }
    job_id = job_backend.enqueue(task_name="forecast", payload=payload)
    return {"job_id": job_id, "model_id": model_id, "status": "queued"}
