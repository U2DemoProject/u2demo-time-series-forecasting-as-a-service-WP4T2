from abc import ABC, abstractmethod
from typing import Any


class DataSource[TConfig](ABC):
    """Abstract data source contract for training/forecast payload retrieval."""

    @abstractmethod
    def fetch(self, config: TConfig) -> dict[str, Any]:
        """Return normalized source payload from provided source configuration."""
        raise NotImplementedError
