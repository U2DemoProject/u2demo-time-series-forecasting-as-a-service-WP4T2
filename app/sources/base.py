from abc import ABC, abstractmethod
from typing import Any

from app.schemas.common import DataSourceConfig


class DataSource(ABC):
    """Abstract data source contract for training/forecast payload retrieval."""

    @abstractmethod
    def fetch(self, config: DataSourceConfig) -> dict[str, Any]:
        """Return normalized source payload from provided source configuration."""
        raise NotImplementedError
