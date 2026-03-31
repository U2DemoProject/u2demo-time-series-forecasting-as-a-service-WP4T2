import hashlib
import json
from pathlib import Path
from typing import Any

import requests

from app.core.errors import ModelNotFoundError, SourceValidationError
from app.repositories.base import ModelRepository
from app.schemas.common import UrlModelSourceConfig


class UrlModelRepository(ModelRepository):
    def __init__(self, cache_dir: Path, source_config: UrlModelSourceConfig) -> None:
        self.cache_dir = cache_dir
        self.source_config = source_config

    def _cache_file(self, model_id: str, version: str) -> Path:
        safe_key = f"{model_id}-{version}.json"
        return self.cache_dir / safe_key

    def _download(self) -> bytes:
        location = self.source_config.location
        try:
            resp = requests.get(
                str(location.url),
                headers=location.headers,
                timeout=location.timeout_seconds,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SourceValidationError(f"Failed to fetch model artifact: {exc}") from exc
        return resp.content

    def save_model(self, model_id: str, version: str, payload: dict[str, Any]) -> str:
        target = self._cache_file(model_id, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(target)

    def load_model(self, model_id: str, version: str) -> dict[str, Any]:
        target = self._cache_file(model_id, version)

        if target.exists():
            return json.loads(target.read_text(encoding="utf-8"))

        body = self._download()
        checksum = self.source_config.location.checksum_sha256
        if checksum:
            digest = hashlib.sha256(body).hexdigest()
            if digest != checksum:
                raise SourceValidationError("Model artifact checksum mismatch")

        try:
            payload = json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise SourceValidationError("Downloaded model artifact is not valid JSON") from exc

        self.save_model(model_id, version, payload)
        return payload

    def model_exists(self, model_id: str, version: str) -> bool:
        return self._cache_file(model_id, version).exists()
