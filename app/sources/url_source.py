from typing import Any

import requests

from app.core.errors import SourceValidationError
from app.schemas.common import UrlDataSourceConfig
from app.sources.base import DataSource


class UrlDataSource(DataSource[UrlDataSourceConfig]):
    """Data source that fetches JSON payload from a remote HTTP endpoint."""

    def fetch(self, config: UrlDataSourceConfig) -> dict[str, Any]:
        """Execute configured HTTP request and return JSON response body."""
        request = config.request

        try:
            response = requests.request(
                method=request.method,
                url=str(request.url),
                headers=request.headers,
                params=request.query,
                json=request.body,
                timeout=request.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceValidationError(f"Failed to fetch URL data source: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise SourceValidationError("Upstream response is not valid JSON") from exc
