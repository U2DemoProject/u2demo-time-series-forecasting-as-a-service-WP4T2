from pathlib import Path

from app.repositories.base import ModelRepository
from app.repositories.url_repository import UrlModelRepository
from app.repositories.volume_repository import VolumeModelRepository
from app.schemas.common import ModelSourceConfig, UrlModelSourceConfig


class ModelRepositoryFactory:
    @staticmethod
    def create(source_config: ModelSourceConfig, models_dir: Path, cache_dir: Path) -> ModelRepository:
        if source_config.type == "volume":
            return VolumeModelRepository(models_dir)

        if source_config.type == "url":
            url_config = UrlModelSourceConfig.model_validate(source_config.model_dump())
            return UrlModelRepository(cache_dir=cache_dir, source_config=url_config)

        raise ValueError(f"Unsupported model source type: {source_config.type}")
