import json
from pathlib import Path
from typing import Any

from app.core.errors import ModelNotFoundError
from app.repositories.base import ModelRepository


class VolumeModelRepository(ModelRepository):
    """Model repository backed by the local mounted storage volume."""

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir

    def _path(self, model_id: str, version: str) -> Path:
        return self.models_dir / model_id / version / "model.json"

    def save_model(self, model_id: str, version: str, payload: dict[str, Any]) -> str:
        """Persist payload JSON to the volume-backed model path."""
        target = self._path(model_id, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(target)

    def load_model(self, model_id: str, version: str) -> dict[str, Any]:
        """Load payload JSON from the volume-backed model path."""
        source = self._path(model_id, version)
        if not source.exists():
            raise ModelNotFoundError(f"Model artifact not found for {model_id}:{version}")
        return json.loads(source.read_text(encoding="utf-8"))

    def model_exists(self, model_id: str, version: str) -> bool:
        """Return whether the volume-backed artifact exists."""
        return self._path(model_id, version).exists()
