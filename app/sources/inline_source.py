from typing import Any

from app.sources.base import DataSource


class InlineDataSource(DataSource):
    def fetch(self, context: dict[str, Any]) -> dict[str, Any]:
        return context
