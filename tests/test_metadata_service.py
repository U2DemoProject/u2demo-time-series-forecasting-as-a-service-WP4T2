"""Unit tests for MetadataService."""

from pathlib import Path

import pytest

from app.core.errors import ModelNotFoundError
from app.schemas.models import CreateModelRequest
from app.services.metadata_service import MetadataService


@pytest.fixture
def svc(tmp_path: Path) -> MetadataService:
    return MetadataService(tmp_path)


def test_create_persists_metadata(svc: MetadataService) -> None:
    req = CreateModelRequest(model_id="m1", description="test model")
    meta = svc.create(req)

    assert meta.model_id == "m1"
    assert meta.description == "test model"
    assert meta.versions == []
    assert (svc.metadata_dir / "m1.json").exists()


def test_get_returns_existing_model(svc: MetadataService) -> None:
    svc.create(CreateModelRequest(model_id="m1"))
    meta = svc.get("m1")
    assert meta.model_id == "m1"


def test_get_raises_for_missing_model(svc: MetadataService) -> None:
    with pytest.raises(ModelNotFoundError):
        svc.get("nonexistent")


def test_list_returns_all_models(svc: MetadataService) -> None:
    svc.create(CreateModelRequest(model_id="a"))
    svc.create(CreateModelRequest(model_id="b"))
    models = svc.list_models()
    assert {m.model_id for m in models} == {"a", "b"}


def test_add_version_appends_and_deduplicates(svc: MetadataService) -> None:
    svc.create(CreateModelRequest(model_id="m1"))

    svc.add_version("m1", "v1")
    svc.add_version("m1", "v2")
    svc.add_version("m1", "v1")  # duplicate — should be ignored

    meta = svc.get("m1")
    assert meta.versions == ["v1", "v2"]


def test_add_version_raises_for_missing_model(svc: MetadataService) -> None:
    with pytest.raises(ModelNotFoundError):
        svc.add_version("ghost", "v1")
