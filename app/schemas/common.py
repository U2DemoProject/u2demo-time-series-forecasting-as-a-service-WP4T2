from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class RetryConfig(BaseModel):
    max_attempts: int = 1
    backoff_seconds: float = 0.0


class UrlRequestConfig(BaseModel):
    method: Literal["GET", "POST"] = "GET"
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout_seconds: int = 30
    retry: RetryConfig = Field(default_factory=RetryConfig)


class InlineDataSourceConfig(BaseModel):
    type: Literal["inline"]
    payload: dict[str, Any]


class UrlDataSourceConfig(BaseModel):
    type: Literal["url"]
    request: UrlRequestConfig


DataSourceConfig = InlineDataSourceConfig | UrlDataSourceConfig


class VolumeModelSourceConfig(BaseModel):
    type: Literal["volume"] = "volume"


class UrlModelLocation(BaseModel):
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    checksum_sha256: str | None = None
    timeout_seconds: int = 60


class UrlModelSourceConfig(BaseModel):
    type: Literal["url"]
    location: UrlModelLocation


ModelSourceConfig = VolumeModelSourceConfig | UrlModelSourceConfig


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    task: str
    model_id: str
    created_at: datetime
    updated_at: datetime
    detail: dict[str, Any] = Field(default_factory=dict)
