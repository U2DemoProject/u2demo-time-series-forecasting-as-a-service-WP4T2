from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field
from u2demo_time_series_forecasting.versioning import parse_forecast_payload, parse_training_payload

from app.schemas.common import DataSourceConfig, ModelSourceConfig
from app.schemas.forecast_models import ForecastInput, ForecastInputV2, ForecastTrainingInput, ForecastTrainingInputV2


def _parse_training(value: object) -> object:
    return parse_training_payload(value) if isinstance(value, dict) else value


def _parse_forecast(value: object) -> object:
    return parse_forecast_payload(value) if isinstance(value, dict) else value


# v1 or v2 payloads; the data model version is detected from the payload.
type TrainingInput = Annotated[ForecastTrainingInput | ForecastTrainingInputV2, BeforeValidator(_parse_training)]
type ForecastingInput = Annotated[ForecastInput | ForecastInputV2, BeforeValidator(_parse_forecast)]


class TrainRequest(BaseModel):
    """
    Training request.

    Provide either ``forecast_training_input`` directly (takes precedence) or
    a ``data_source`` whose payload is a ``ForecastTrainingInput`` or
    ``ForecastTrainingInputV2``-shaped dict (useful for fetching training data
    from a remote URL). The data model version (v1 or v2) is detected from the payload.
    """

    data_source: DataSourceConfig | None = Field(
        default=None,
        description="Data source whose payload is a v1 or v2 training input dict (inline or URL).",
    )
    forecast_training_input: TrainingInput | None = Field(
        default=None,
        description="Typed v1 or v2 training input (takes precedence over data_source payload).",
    )
    model_source: ModelSourceConfig | None = Field(
        default=None,
        description="Where to persist the trained model artifact. Defaults to local volume.",
    )


class ForecastRequest(BaseModel):
    """
    Forecast request.

    Provide either ``forecast_input`` directly (takes precedence) or a
    ``data_source`` whose payload is a ``ForecastInput`` or ``ForecastInputV2``-shaped
    dict. The forecast is returned in the data model version of the input.
    ``version`` overrides the model version resolved from metadata when set to
    something other than ``'latest'``.
    """

    version: str = Field(
        default="latest",
        description="Model version to use. 'latest' resolves to the most recently trained version.",
    )
    data_source: DataSourceConfig | None = Field(
        default=None,
        description="Data source whose payload is a v1 or v2 forecast input dict (inline or URL).",
    )
    forecast_input: ForecastingInput | None = Field(
        default=None,
        description="Typed v1 or v2 forecast input (takes precedence over data_source payload).",
    )
    model_source: ModelSourceConfig | None = Field(
        default=None,
        description="Where to load the model artifact from. Defaults to local volume.",
    )
