from abc import ABC, abstractmethod
from pathlib import Path


class ModelRepository(ABC):
    """Abstract interface for storing and loading model artifacts."""

    @abstractmethod
    def save_model(self, model_id: str, version: str, source_dir: Path) -> str:
        """Persist source_dir/{model_id}_{version}/ to durable storage. Returns location."""
        raise NotImplementedError

    @abstractmethod
    def load_model(self, model_id: str, version: str, target_dir: Path) -> Path:
        """Materialize artifact under target_dir/{model_id}_{version}/. Returns that path."""
        raise NotImplementedError

    @abstractmethod
    def model_exists(self, model_id: str, version: str) -> bool:
        """Check whether model artifact exists for an id/version pair."""
        raise NotImplementedError
