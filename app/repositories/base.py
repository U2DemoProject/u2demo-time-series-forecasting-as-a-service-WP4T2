from abc import ABC, abstractmethod
from typing import Any


class ModelRepository(ABC):
    @abstractmethod
    def save_model(self, model_id: str, version: str, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def load_model(self, model_id: str, version: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def model_exists(self, model_id: str, version: str) -> bool:
        raise NotImplementedError
