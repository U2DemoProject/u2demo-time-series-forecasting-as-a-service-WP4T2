from app.schemas.common import InlineDataSourceConfig, UrlDataSourceConfig
from app.sources.base import DataSource
from app.sources.inline_source import InlineDataSource
from app.sources.url_source import UrlDataSource


class DataSourceFactory:
    """Factory for resolving concrete data source implementations."""

    @staticmethod
    def create(config: InlineDataSourceConfig | UrlDataSourceConfig) -> DataSource:
        """Instantiate a data source based on the provided config type."""
        if config.type == "inline":
            return InlineDataSource()
        if config.type == "url":
            return UrlDataSource()
        raise ValueError(f"Unsupported data source type: {config.type}")
