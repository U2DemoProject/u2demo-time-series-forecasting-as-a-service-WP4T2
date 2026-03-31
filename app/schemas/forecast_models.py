from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, StringConstraints


QuantileKey: TypeAlias = Annotated[str, StringConstraints(pattern=r"^(0(\.\d+)?|1(\.0+)?)$")]
QuantileLevel: TypeAlias = Annotated[float, Field(ge=0, le=1)]


class TimeValue(BaseModel):
    """Generic timestamp–value pair aligned with SAREF (saref:hasTimestamp, saref:hasValue)."""
    time: datetime = Field(..., description="Timestamp of the measurement")
    value: float = Field(..., description="Measured or scheduled numeric value")


class ForecastedTimeValue(TimeValue):
    """Extends TimeValue with probabilistic forecast information."""
    quantiles: dict[QuantileKey, float] | None = Field(
        default=None,
        description="Quantile predictions at this timestep. Keys are quantile levels (0-1), values are the predicted value at that quantile."
    )


ForecastType: TypeAlias = Literal["deterministic", "stochastic"]


class TimeParameters(BaseModel):
    """Time-related configuration parameters for forecasting."""
    timestep_minutes: int | None = Field(
        default=None, ge=1, description="Length of a single time step in minutes."
    )
    horizon_hours: int | None = Field(
        default=None, ge=1, description="Planning horizon length in hours."
    )
    scheduling_time: datetime | None = Field(
        default=None,
        description="Time at which the forecasting is executed."
    )


class TrainingSplit(BaseModel):
    """Train/validation/test split configuration."""
    train_ratio: float = Field(
        default=0.7, ge=0, le=1, description="Fraction of data used for training."
    )
    validation_ratio: float = Field(
        default=0.15, ge=0, le=1, description="Fraction of data used for validation."
    )
    test_ratio: float = Field(
        default=0.15, ge=0, le=1, description="Fraction of data used for testing."
    )


class ModelConfig(BaseModel):
    """Configuration parameters for the training process."""
    model_config = ConfigDict(extra="allow")

    model_id: str = Field(..., description="Unique identifier for this model instance.")
    model_preset: str | None = Field(
        default="Chronos2Model",
        description="ML algorithm or architecture preset."
    )
    model_version: str | None = Field(
        default=None, description="Version identifier for the model (e.g., '1.0.0')."
    )
    training_split: TrainingSplit = Field(
        default_factory=TrainingSplit,
        description="Train/validation/test split configuration."
    )
    lookback_steps: int | None = Field(
        default=None, ge=1, description="Number of past timesteps used as input features."
    )
    loss_function: str | None = Field(
        default=None, description="Loss function to optimize (e.g., 'mse', 'mae')."
    )
    quantile_levels: list[QuantileLevel] | None = Field(
        default=None,
        description="Quantile levels to predict (for quantile regression models)."
    )

class BaseSeries(BaseModel):
    """Common identified time series metadata."""
    model_config = ConfigDict(extra="allow")

    series_id: str = Field(..., description="Unique identifier for this series.")
    variable_name: str = Field(..., description="Name of the variable to forecast.")
    asset_id: str | None = Field(
        default=None, description="Identifier of the asset this series belongs to."
    )
    asset_type: str | None = Field(
        default=None, description="Type of the asset (e.g., 'PV', 'WindTurbine', 'Load')."
    )
    unit: str | None = Field(default=None, description="Unit of measurement.")
    unitIri: AnyUrl | None = Field(
        default=None, description="QUDT URI for the unit."
    )

class TrainingTargetSeries(BaseSeries):
    """Target series shape used by ForecastTrainingInputDM."""
    training_values: list[TimeValue] = Field(
        ...,
        min_length=2,
        description="Full historical ground truth time series used for training."
    )


class ForecastTargetSeries(BaseSeries):
    """Target series shape used by ForecastInputDM."""
    historical_values: list[TimeValue] = Field(
        ...,
        min_length=1,
        description="Past observations of the target variable used as input for forecast."
    )


class BaseExogenousSeries(BaseModel):
    """Common exogenous time series metadata."""
    model_config = ConfigDict(extra="allow")

    series_id: str = Field(..., description="Unique identifier for this exogenous series.")
    variable_name: str = Field(..., description="Name of the exogenous variable.")
    source: str | None = Field(default=None, description="Data source or provider.")
    unit: str | None = Field(default=None, description="Unit of measurement.")
    unitIri: AnyUrl | None = Field(default=None, description="QUDT URI for the unit.")

class TrainingExogenousSeries(BaseExogenousSeries):
    """Exogenous series shape used by ForecastTrainingInputDM."""
    training_values: list[TimeValue] | None = Field(
        ...,
        min_length=2,
        description="Full historical ground truth time series used for training."
    )


class ForecastExogenousSeries(BaseExogenousSeries):
    """Exogenous series shape used by ForecastInputDM."""
    historical_values: list[TimeValue] = Field(
        ...,
        min_length=1,
        description="Historical values aligned with target_series for forecast."
    )
    future_values: list[TimeValue] | None = Field(
        default=None,
        description="Known or forecasted future values over the forecast horizon."
    )


class Location(BaseModel):
    """Geographic location aligned with WGS84."""
    latitude: float = Field(ge=-90, le=90, description="Latitude in decimal degrees (WGS84).")
    longitude: float = Field(ge=-180, le=180, description="Longitude in decimal degrees (WGS84).")


class ForecastTrainingInput(BaseModel):
    """Input data model for training a forecasting model."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    forecast_type: ForecastType = Field(
        ..., description="Type of forecast model to train."
    )
    time_parameters: TimeParameters = Field(
        ..., description="Target forecast resolution and horizon the model should learn."
    )
    training_model_config: ModelConfig = Field(
        ...,
        alias="model_config",
        serialization_alias="model_config",
        description="Configuration parameters for the training process."
    )
    target_series: TrainingTargetSeries = Field(
        ..., description="The target variable with ground truth data for training."
    )
    location: Location | None = Field(
        default=None, description="Geographic location of the asset."
    )
    exogenous_series: list[TrainingExogenousSeries] | None = Field(
        default=None,
        description="Optional additional time series of external variables."
    )

class ForecastInput(BaseModel):
    """Input data model for a forecasting request."""
    model_config = ConfigDict(extra="allow")

    forecast_type: ForecastType = Field(
        ..., description="Desired forecast output type."
    )
    time_parameters: TimeParameters = Field(
        ..., description="Forecast horizon and time resolution parameters."
    )
    model_id: str | None = Field(default=None, description="Unique identifier for the model to use for forecast.")
    target_series: ForecastTargetSeries = Field(
        ..., description="The primary variable to be forecasted."
    )
    location: Location | None = Field(
        default=None,
        description="Geographic location of the asset. Useful for weather-dependent forecasts."
    )
    exogenous_series: list[ForecastExogenousSeries] | None = Field(
        default=None,
        description="Optional additional time series of external variables."
    )

class ForecastSeries(BaseModel):
    """A forecast time series for a specific variable/asset combination."""
    model_config = ConfigDict(extra="allow")

    series_id: str = Field(..., description="Unique identifier for this forecast series.")
    variable_name: str = Field(..., description="Name of the forecasted variable.")
    asset_id: str | None = Field(
        default=None, description="Identifier of the asset this forecast relates to."
    )
    asset_type: str | None = Field(
        default=None, description="Type of the asset (e.g., 'PV', 'WindTurbine', 'Load')."
    )
    unit: str | None = Field(default=None, description="Unit of measurement.")
    unitIri: str | None = Field(default=None, description="QUDT URI for the unit.")
    values: list[ForecastedTimeValue] = Field(
        ..., min_items=1, description="Time series of forecasted values."
    )

class Forecast(BaseModel):
    """Forecast data model with identified time series and optional probabilistic information."""
    model_config = ConfigDict(extra="allow")

    forecast_type: ForecastType = Field(
        ..., description="Type of forecast."
    )
    forecast_date: datetime = Field(..., description="Generation time of the forecast.")
    time_parameters: TimeParameters | None = Field(
        default=None, description="Time resolution and horizon parameters for this forecast."
    )
    forecast_series: list[ForecastSeries] = Field(
        ..., min_items=1, description="Array of identified forecast time series."
    )

