from functools import lru_cache

from app.core.config import get_settings
from app.jobs.backends import InMemoryJobBackend, JobBackend, RedisRQBackend


@lru_cache(maxsize=1)
def get_job_backend() -> JobBackend:
    """Return cached job backend implementation based on settings."""
    settings = get_settings()

    if settings.jobs_backend == "memory":
        return InMemoryJobBackend()

    return RedisRQBackend(
        redis_url=settings.redis_url,
        handler_map={
            "train": "app.jobs.handlers.train_task",
            "forecast": "app.jobs.handlers.forecast_task",
        },
    )
