from app.schemas.common import InlineDataSourceConfig
from app.sources.base import DataSource


class InlineDataSource(DataSource):
    """Data source that directly returns inline request payload content."""

    def fetch(self, config: InlineDataSourceConfig) -> dict[str, Any]:
        """Return inline payload without additional transformation."""
        return config.payload
