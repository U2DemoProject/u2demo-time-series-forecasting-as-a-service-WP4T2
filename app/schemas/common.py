from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class RetryConfig(BaseModel):
    """Retry strategy for upstream URL requests."""

    max_attempts: int = 1
    backoff_seconds: float = 0.0


class UrlRequestConfig(BaseModel):
    """HTTP request configuration for URL-based data retrieval."""

    method: Literal["GET", "POST"] = "GET"
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout_seconds: int = 30
    retry: RetryConfig = Field(default_factory=RetryConfig)


class InlineDataSourceConfig(BaseModel):
    """Inline payload-based data source configuration."""

    type: Literal["inline"]
    payload: dict[str, Any]


class UrlDataSourceConfig(BaseModel):
    """URL-based data source configuration."""

    type: Literal["url"]
    request: UrlRequestConfig


DataSourceConfig = InlineDataSourceConfig | UrlDataSourceConfig


class VolumeModelSourceConfig(BaseModel):
    """Local volume model source configuration."""

    type: Literal["volume"] = "volume"


class UrlModelLocation(BaseModel):
    """Remote model artifact location and validation options."""

    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    checksum_sha256: str | None = None
    timeout_seconds: int = 60


class UrlModelSourceConfig(BaseModel):
    """URL-based model source configuration."""

    type: Literal["url"]
    location: UrlModelLocation


ModelSourceConfig = VolumeModelSourceConfig | UrlModelSourceConfig


class JobStatus(BaseModel):
    """Normalized job status response schema."""

    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    task: str
    model_id: str
    created_at: datetime
    updated_at: datetime
    detail: dict[str, Any] = Field(default_factory=dict)
