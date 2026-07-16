import os
import tarfile
from pathlib import Path

from app.core.errors import ModelNotFoundError
from app.repositories.base import ModelRepository


class VolumeModelRepository(ModelRepository):
    """Model repository backed by the local mounted storage volume."""

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir

    def _path(self, model_id: str, version: str) -> Path:
        return self.models_dir / model_id / f"{version}.tar.gz"

    def save_model(self, model_id: str, version: str, source_dir: Path) -> str:
        """Tar+gzip source_dir/{model_id}_{version}/ into the volume tarball atomically."""
        artifact_name = f"{model_id}_{version}"
        artifact_path = source_dir / artifact_name
        target = self._path(model_id, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(target) + ".tmp")
        with tarfile.open(tmp, "w:gz") as tf:
            tf.add(artifact_path, arcname=artifact_name)
        os.replace(tmp, target)
        return str(target)

    def load_model(self, model_id: str, version: str, target_dir: Path) -> Path:
        """Extract tarball into target_dir and return the artifact subdirectory path."""
        source = self._path(model_id, version)
        if not source.exists():
            raise ModelNotFoundError(f"Model artifact not found for {model_id}:{version}")
        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(source, "r:gz") as tf:
            tf.extractall(target_dir, filter="data")
        return target_dir / f"{model_id}_{version}"

    def model_exists(self, model_id: str, version: str) -> bool:
        """Return whether the tarball exists on the volume."""
        return self._path(model_id, version).exists()
