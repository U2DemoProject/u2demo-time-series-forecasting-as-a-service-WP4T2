from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateModelRequest(BaseModel):
    """Request payload for creating model metadata."""

    model_id: str
    description: str | None = None
    target: str | None = None
    time_column: str | None = None
    id_column: str | None = None
    freq: str | None = None


class ModelMetadata(BaseModel):
    """Persisted metadata representation for a model."""

    model_id: str
    description: str | None = None
    target: str | None = None
    time_column: str | None = None
    id_column: str | None = None
    freq: str | None = None
    versions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ModelInfoResponse(BaseModel):
    """Response schema for a single model lookup."""

    metadata: ModelMetadata


class ModelListResponse(BaseModel):
    """Response schema listing all available model metadata records."""

    models: list[ModelMetadata] = Field(default_factory=list)


class ForecastResponse(BaseModel):
    """Response schema for forecast output payloads."""

    model_id: str
    version: str
    horizon: int
    predictions: list[dict[str, Any]]
