"""Unit tests for VolumeModelRepository — filesystem round-trips."""

import tarfile
from pathlib import Path

import pytest

from app.core.errors import ModelNotFoundError
from app.repositories.volume_repository import VolumeModelRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifact(base: Path, model_id: str, version: str) -> Path:
    """Create a fake artifact directory tree under base and return its path."""
    artifact = base / f"{model_id}_{version}"
    (artifact / "subdir").mkdir(parents=True)
    (artifact / "model.pkl").write_bytes(b"\x80\x04fake-pickle-data")
    (artifact / "subdir" / "weights.bin").write_bytes(b"\x00\x01\x02\x03")
    return artifact


# ---------------------------------------------------------------------------
# save_model
# ---------------------------------------------------------------------------


def test_save_model_creates_tarball(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_artifact(source_dir, "m", "v1")

    location = repo.save_model("m", "v1", source_dir)

    tarball = tmp_path / "models" / "m" / "v1.tar.gz"
    assert tarball.exists()
    assert location == str(tarball)


def test_save_model_tarball_contains_artifact_dir(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_artifact(source_dir, "m", "v1")

    repo.save_model("m", "v1", source_dir)

    tarball = tmp_path / "models" / "m" / "v1.tar.gz"
    with tarfile.open(tarball, "r:gz") as tf:
        names = tf.getnames()

    assert "m_v1" in names
    assert "m_v1/model.pkl" in names
    assert "m_v1/subdir/weights.bin" in names


def test_save_model_is_atomic(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_artifact(source_dir, "m", "v1")

    repo.save_model("m", "v1", source_dir)

    models_dir = tmp_path / "models" / "m"
    tmp_files = list(models_dir.glob("*.tmp"))
    assert tmp_files == [], "No .tmp file should remain after save"


def test_save_model_creates_parent_dirs(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models" / "deep" / "path")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_artifact(source_dir, "m", "v1")

    repo.save_model("m", "v1", source_dir)

    assert (tmp_path / "models" / "deep" / "path" / "m" / "v1.tar.gz").exists()


# ---------------------------------------------------------------------------
# load_model
# ---------------------------------------------------------------------------


def test_load_model_extracts_artifact(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_artifact(source_dir, "m", "v1")
    repo.save_model("m", "v1", source_dir)

    extract_dir = tmp_path / "extract"
    result_path = repo.load_model("m", "v1", extract_dir)

    assert result_path == extract_dir / "m_v1"
    assert (result_path / "model.pkl").read_bytes() == b"\x80\x04fake-pickle-data"
    assert (result_path / "subdir" / "weights.bin").read_bytes() == b"\x00\x01\x02\x03"


def test_load_model_raises_for_missing_version(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    with pytest.raises(ModelNotFoundError):
        repo.load_model("m", "v99", tmp_path / "extract")


# ---------------------------------------------------------------------------
# model_exists
# ---------------------------------------------------------------------------


def test_model_exists_returns_true_after_save(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _make_artifact(source_dir, "m", "v1")
    repo.save_model("m", "v1", source_dir)

    assert repo.model_exists("m", "v1") is True


def test_model_exists_returns_false_before_save(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    assert repo.model_exists("m", "v1") is False


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_binary_content(tmp_path: Path) -> None:
    repo = VolumeModelRepository(tmp_path / "models")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    artifact = _make_artifact(source_dir, "mymodel", "20260101")
    original_bytes = (artifact / "model.pkl").read_bytes()

    repo.save_model("mymodel", "20260101", source_dir)

    extract_dir = tmp_path / "extract"
    result = repo.load_model("mymodel", "20260101", extract_dir)
    assert (result / "model.pkl").read_bytes() == original_bytes
