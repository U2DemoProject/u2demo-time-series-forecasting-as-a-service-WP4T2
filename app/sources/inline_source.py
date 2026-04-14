from typing import Any

from app.sources.base import DataSource


class InlineDataSource(DataSource):
    """Data source that directly returns inline request payload content."""

    def fetch(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return inline payload without additional transformation."""
        return context
