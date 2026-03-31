from abc import ABC, abstractmethod
from typing import Any


class DataSource(ABC):
    @abstractmethod
    def fetch(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
