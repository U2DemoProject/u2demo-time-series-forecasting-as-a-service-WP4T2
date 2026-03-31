from typing import Any

import requests

from app.core.errors import SourceValidationError
from app.schemas.common import UrlRequestConfig
from app.sources.base import DataSource


class UrlDataSource(DataSource):
    def fetch(self, context: dict[str, Any]) -> dict[str, Any]:
        request = UrlRequestConfig.model_validate(context)

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
