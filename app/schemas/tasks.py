from pydantic import BaseModel, Field

from app.schemas.common import DataSourceConfig
from app.schemas.forecast_models import ForecastInput, ForecastTrainingInput


class TrainRequest(BaseModel):
    """
    Training request.

    Provide either ``forecast_training_input`` directly (takes precedence) or
    a ``data_source`` whose payload is a ``ForecastTrainingInput``-shaped dict
    (useful for fetching training data from a remote URL).
    """

    data_source: DataSourceConfig | None = Field(
        default=None,
        description="Data source whose payload is a ForecastTrainingInput dict (inline or URL).",
    )
    forecast_training_input: ForecastTrainingInput | None = Field(
        default=None,
        description="Typed training input (takes precedence over data_source payload).",
    )


class ForecastRequest(BaseModel):
    """
    Forecast request.

    Provide either ``forecast_input`` directly (takes precedence) or a
    ``data_source`` whose payload is a ``ForecastInput``-shaped dict.
    ``version`` overrides the model version resolved from metadata when set to
    something other than ``'latest'``.
    """

    version: str = Field(
        default="latest",
        description="Model version to use. 'latest' resolves to the most recently trained version.",
    )
    data_source: DataSourceConfig | None = Field(
        default=None,
        description="Data source whose payload is a ForecastInput dict (inline or URL).",
    )
    forecast_input: ForecastInput | None = Field(
        default=None,
        description="Typed forecast input (takes precedence over data_source payload).",
    )
