import os

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

# Propagate the configured models directory to the u2 library, which reads
# MODEL_PATH from the environment at call time.
os.environ.setdefault("MODEL_PATH", str(settings.models_dir))

app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness probe endpoint."""
    return {"status": "ready"}
