from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import DataSourceConfig, ModelSourceConfig, VolumeModelSourceConfig
from app.schemas.forecast_models import ForecastInput, ForecastTrainingInput


class TrainRequest(BaseModel):
    """Training request with data source and optional forecast training input schema."""

    data_source: DataSourceConfig = Field(
        ..., description="Data source configuration (inline or URL)."
    )
    forecast_training_input: ForecastTrainingInput | None = Field(
        default=None,
        description="Optional forecast-specific training input schema with model config, time parameters, and metadata."
    )
    hyperparameters: dict[str, Any] = Field(
        default_factory=dict, description="Additional hyperparameters for training."
    )
    model_source: ModelSourceConfig = Field(
        default_factory=VolumeModelSourceConfig,
        description="Model storage source configuration."
    )


class ForecastRequest(BaseModel):
    """Forecast request with data source and optional forecast input schema."""

    version: str = Field(
        default="latest", description="Model version to use for forecast."
    )
    horizon: int = Field(
        default=1, ge=1, description="Number of timesteps to forecast."
    )
    data_source: DataSourceConfig = Field(
        ..., description="Data source configuration (inline or URL)."
    )
    forecast_input: ForecastInput | None = Field(
        default=None,
        description="Optional forecast-specific input schema with time parameters and location."
    )
    model_source: ModelSourceConfig = Field(
        default_factory=VolumeModelSourceConfig,
        description="Model storage source configuration."
    )
