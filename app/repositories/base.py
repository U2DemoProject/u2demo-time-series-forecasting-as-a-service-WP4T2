from abc import ABC, abstractmethod
from typing import Any


class ModelRepository(ABC):
    """Abstract interface for storing and loading model artifacts."""

    @abstractmethod
    def save_model(self, model_id: str, version: str, payload: dict[str, Any]) -> str:
        """Persist model payload and return storage location."""
        raise NotImplementedError

    @abstractmethod
    def load_model(self, model_id: str, version: str) -> dict[str, Any]:
        """Load model payload for an id/version pair."""
        raise NotImplementedError

    @abstractmethod
    def model_exists(self, model_id: str, version: str) -> bool:
        """Check whether model payload exists for an id/version pair."""
        raise NotImplementedError
