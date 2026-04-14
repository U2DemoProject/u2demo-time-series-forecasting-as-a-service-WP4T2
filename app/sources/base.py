from abc import ABC, abstractmethod
from typing import Any


class DataSource(ABC):
    """Abstract data source contract for training/forecast payload retrieval."""

    @abstractmethod
    def fetch(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return normalized source payload from provided context."""
        raise NotImplementedError
