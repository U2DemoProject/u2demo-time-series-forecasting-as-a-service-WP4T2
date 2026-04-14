import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.errors import ModelNotFoundError
from app.schemas.models import CreateModelRequest, ModelMetadata


class MetadataService:
    """Service for reading and writing model metadata JSON files."""

    def __init__(self, metadata_dir: Path) -> None:
        self.metadata_dir = metadata_dir

    def _path(self, model_id: str) -> Path:
        return self.metadata_dir / f"{model_id}.json"

    def create(self, payload: CreateModelRequest) -> ModelMetadata:
        """Create and persist metadata for a new model id."""
        now = datetime.now(UTC)
        metadata = ModelMetadata(
            model_id=payload.model_id,
            description=payload.description,
            target=payload.target,
            time_column=payload.time_column,
            id_column=payload.id_column,
            freq=payload.freq,
            versions=[],
            created_at=now,
            updated_at=now,
        )
        self._path(payload.model_id).write_text(
            metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return metadata

    def get(self, model_id: str) -> ModelMetadata:
        """Load metadata for a model id."""
        path = self._path(model_id)
        if not path.exists():
            raise ModelNotFoundError(f"Model metadata not found for model_id={model_id}")
        return ModelMetadata.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list_models(self) -> list[ModelMetadata]:
        """Load and return all metadata records from storage."""
        return [
            ModelMetadata.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self.metadata_dir.glob("*.json"))
        ]

    def add_version(self, model_id: str, version: str) -> ModelMetadata:
        """Append a trained version to metadata and persist changes."""
        metadata = self.get(model_id)
        if version not in metadata.versions:
            metadata.versions.append(version)
        metadata.updated_at = datetime.now(UTC)
        self._path(model_id).write_text(metadata.model_dump_json(indent=2), encoding="utf-8")
        return metadata
