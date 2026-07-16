from datetime import datetime
from typing import Annotated, Any, Literal

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


class EnvRef(BaseModel):
    """Reference to a secret stored in an environment variable."""

    env: str


class HttpBasicAuth(BaseModel):
    """HTTP Basic authentication credentials."""

    username: str | EnvRef
    password: str | EnvRef


class HttpBearerAuth(BaseModel):
    """HTTP Bearer token authentication."""

    token: str | EnvRef


class SftpPasswordAuth(BaseModel):
    """SFTP password authentication."""

    password: str | EnvRef


class SftpKeyAuth(BaseModel):
    """SFTP private-key authentication."""

    private_key_path: str | EnvRef


class HttpModelLocation(BaseModel):
    """Remote model artifact location over HTTP/HTTPS with optional auth and upload config."""

    scheme: Literal["http", "https"] = "https"
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    upload_method: Literal["PUT", "POST"] = "PUT"
    auth: HttpBasicAuth | HttpBearerAuth | None = None
    checksum_sha256: str | None = None
    timeout_seconds: int = 60


class SftpModelLocation(BaseModel):
    """Remote model artifact location over SFTP."""

    scheme: Literal["sftp"]
    host: str
    port: int = 22
    username: str
    remote_path: str
    auth: SftpPasswordAuth | SftpKeyAuth
    checksum_sha256: str | None = None
    timeout_seconds: int = 60


UrlModelLocation = Annotated[
    HttpModelLocation | SftpModelLocation,
    Field(discriminator="scheme"),
]


class UrlModelSourceConfig(BaseModel):
    """URL-based model source configuration."""

    type: Literal["url"]
    location: UrlModelLocation


ModelSourceConfig = VolumeModelSourceConfig | UrlModelSourceConfig


JobState = Literal["queued", "running", "succeeded", "failed"]


class JobStatus(BaseModel):
    """
    Normalized job status returned by ``GET /jobs/{job_id}``.

    ``status`` uses a backend-independent vocabulary so clients poll for the
    same values regardless of the execution backend (RQ/Redis or in-memory):

    - ``queued``    — accepted, not started yet
    - ``running``   — executing on a worker
    - ``succeeded`` — finished; the payload is in ``detail['result']``
    - ``failed``    — errored; the traceback is in ``detail['error']``

    ``model_id``/``created_at``/``updated_at`` are best-effort and may be
    ``None`` depending on what the backend is able to report.
    """

    job_id: str
    status: JobState
    task: str
    model_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
