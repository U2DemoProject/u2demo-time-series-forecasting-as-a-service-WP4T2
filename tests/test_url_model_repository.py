"""Unit tests for UrlModelRepository — HTTP and SFTP transports."""

import hashlib
import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import SourceValidationError
from app.repositories.url_repository import UrlModelRepository
from app.schemas.common import (
    EnvRef,
    HttpBasicAuth,
    HttpBearerAuth,
    HttpModelLocation,
    SftpKeyAuth,
    SftpModelLocation,
    SftpPasswordAuth,
    UrlModelSourceConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifact_tarball(model_id: str, version: str) -> bytes:
    artifact_name = f"{model_id}_{version}"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        content = b"\x80\x04fake-pickle-data"
        info = tarfile.TarInfo(name=f"{artifact_name}/model.pkl")
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _http_repo(cache_dir: Path, url: str = "https://example.com/model.tar.gz") -> UrlModelRepository:
    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(scheme="https", url=url),  # type: ignore[arg-type]
    )
    return UrlModelRepository(cache_dir=cache_dir, source_config=config)


def _sftp_repo(cache_dir: Path) -> UrlModelRepository:
    config = UrlModelSourceConfig(
        type="url",
        location=SftpModelLocation(
            scheme="sftp",
            host="sftp.example.com",
            username="user",
            remote_path="/models/m_v1.tar.gz",
            auth=SftpPasswordAuth(password="secret"),
        ),
    )
    return UrlModelRepository(cache_dir=cache_dir, source_config=config)


# ---------------------------------------------------------------------------
# HTTP load_model
# ---------------------------------------------------------------------------


def test_http_load_model_fetches_and_extracts(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    repo = _http_repo(tmp_path / "cache")

    mock_resp = MagicMock()
    mock_resp.content = tarball
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp) as mock_get:
        result = repo.load_model("m", "v1", tmp_path / "extract")

    mock_get.assert_called_once()
    assert result == tmp_path / "extract" / "m_v1"
    assert (result / "model.pkl").read_bytes() == b"\x80\x04fake-pickle-data"


def test_http_load_model_caches_tarball(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    repo = _http_repo(tmp_path / "cache")

    mock_resp = MagicMock()
    mock_resp.content = tarball
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp):
        repo.load_model("m", "v1", tmp_path / "extract1")

    assert (tmp_path / "cache" / "m-v1.tar.gz").exists()


def test_http_load_model_uses_cache_on_second_call(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "m-v1.tar.gz").write_bytes(tarball)

    repo = _http_repo(cache_dir)

    with patch("app.repositories.url_repository.requests.get") as mock_get:
        repo.load_model("m", "v1", tmp_path / "extract")

    mock_get.assert_not_called()


def test_http_load_model_raises_on_checksum_mismatch(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(
            scheme="https",
            url="https://example.com/model.tar.gz",  # type: ignore[arg-type]
            checksum_sha256="deadbeef" * 8,
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    mock_resp = MagicMock()
    mock_resp.content = tarball
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp), pytest.raises(SourceValidationError, match="checksum"):
        repo.load_model("m", "v1", tmp_path / "extract")


def test_http_load_model_passes_valid_checksum(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    checksum = hashlib.sha256(tarball).hexdigest()
    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(
            scheme="https",
            url="https://example.com/model.tar.gz",  # type: ignore[arg-type]
            checksum_sha256=checksum,
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    mock_resp = MagicMock()
    mock_resp.content = tarball
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp):
        result = repo.load_model("m", "v1", tmp_path / "extract")

    assert result.exists()


# ---------------------------------------------------------------------------
# HTTP save_model
# ---------------------------------------------------------------------------


def test_http_save_model_sends_put(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    artifact = source_dir / "m_v1"
    artifact.mkdir()
    (artifact / "model.pkl").write_bytes(b"data")

    repo = _http_repo(tmp_path / "cache")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.request", return_value=mock_resp) as mock_req:
        location = repo.save_model("m", "v1", source_dir)

    mock_req.assert_called_once()
    call_kwargs = mock_req.call_args
    assert call_kwargs[0][0] == "PUT"
    assert location == "https://example.com/model.tar.gz"


def test_http_save_model_uses_post_when_configured(tmp_path: Path) -> None:
    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(
            scheme="https",
            url="https://example.com/model.tar.gz",  # type: ignore[arg-type]
            upload_method="POST",
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "m_v1").mkdir()
    (source_dir / "m_v1" / "model.pkl").write_bytes(b"data")

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.request", return_value=mock_resp) as mock_req:
        repo.save_model("m", "v1", source_dir)

    assert mock_req.call_args[0][0] == "POST"


# ---------------------------------------------------------------------------
# HTTP auth — env-var indirection
# ---------------------------------------------------------------------------


def test_http_bearer_auth_resolves_env_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "secret-token-value")

    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(
            scheme="https",
            url="https://example.com/model.tar.gz",  # type: ignore[arg-type]
            auth=HttpBearerAuth(token=EnvRef(env="MY_TOKEN")),
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    tarball = _make_artifact_tarball("m", "v1")
    mock_resp = MagicMock()
    mock_resp.content = tarball
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp) as mock_get:
        repo.load_model("m", "v1", tmp_path / "extract")

    headers_used = mock_get.call_args[1]["headers"]
    assert headers_used.get("Authorization") == "Bearer secret-token-value"


def test_http_basic_auth_resolves_env_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_USER", "alice")
    monkeypatch.setenv("MY_PASS", "hunter2")

    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(
            scheme="https",
            url="https://example.com/model.tar.gz",  # type: ignore[arg-type]
            auth=HttpBasicAuth(username=EnvRef(env="MY_USER"), password=EnvRef(env="MY_PASS")),
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    tarball = _make_artifact_tarball("m", "v1")
    mock_resp = MagicMock()
    mock_resp.content = tarball
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp) as mock_get:
        repo.load_model("m", "v1", tmp_path / "extract")

    auth_used = mock_get.call_args[1]["auth"]
    assert auth_used == ("alice", "hunter2")


def test_resolve_secret_raises_when_env_var_missing(tmp_path: Path) -> None:
    config = UrlModelSourceConfig(
        type="url",
        location=HttpModelLocation(
            scheme="https",
            url="https://example.com/model.tar.gz",  # type: ignore[arg-type]
            auth=HttpBearerAuth(token=EnvRef(env="DEFINITELY_NOT_SET_XYZ")),
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    mock_resp = MagicMock()
    mock_resp.content = _make_artifact_tarball("m", "v1")
    mock_resp.raise_for_status = MagicMock()

    with patch("app.repositories.url_repository.requests.get", return_value=mock_resp), pytest.raises(SourceValidationError, match="DEFINITELY_NOT_SET_XYZ"):
        repo.load_model("m", "v1", tmp_path / "extract")


# ---------------------------------------------------------------------------
# HTTP model_exists
# ---------------------------------------------------------------------------


def test_http_model_exists_returns_true_from_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "m-v1.tar.gz").write_bytes(b"whatever")

    repo = _http_repo(cache_dir)
    assert repo.model_exists("m", "v1") is True


def test_http_model_exists_returns_true_from_head(tmp_path: Path) -> None:
    repo = _http_repo(tmp_path / "cache")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("app.repositories.url_repository.requests.head", return_value=mock_resp):
        assert repo.model_exists("m", "v1") is True


def test_http_model_exists_returns_false_on_404(tmp_path: Path) -> None:
    repo = _http_repo(tmp_path / "cache")

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("app.repositories.url_repository.requests.head", return_value=mock_resp):
        assert repo.model_exists("m", "v1") is False


# ---------------------------------------------------------------------------
# SFTP — skipped unless paramiko is installed
# ---------------------------------------------------------------------------

paramiko = pytest.importorskip("paramiko", reason="paramiko not installed; run `poetry install` to enable SFTP tests")


def _mock_ssh_client(tarball: bytes) -> MagicMock:
    """Return a mock SSHClient whose SFTP channel writes tarball to the local cache path."""
    ssh = MagicMock()
    sftp = MagicMock()
    ssh.__enter__ = MagicMock(return_value=sftp)
    ssh.__exit__ = MagicMock(return_value=False)
    ssh.open_sftp.return_value.__enter__ = MagicMock(return_value=sftp)
    ssh.open_sftp.return_value.__exit__ = MagicMock(return_value=False)

    def _fake_get(_remote: str, local: str) -> None:
        Path(local).write_bytes(tarball)

    sftp.get.side_effect = _fake_get
    return ssh, sftp


def test_sftp_load_model_fetches_and_extracts(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    repo = _sftp_repo(tmp_path / "cache")

    ssh_mock, _sftp = _mock_ssh_client(tarball)

    with patch.object(repo, "_sftp_connect", return_value=ssh_mock):
        result = repo.load_model("m", "v1", tmp_path / "extract")

    assert result == tmp_path / "extract" / "m_v1"
    assert (result / "model.pkl").read_bytes() == b"\x80\x04fake-pickle-data"


def test_sftp_load_model_caches_tarball(tmp_path: Path) -> None:
    tarball = _make_artifact_tarball("m", "v1")
    repo = _sftp_repo(tmp_path / "cache")

    ssh_mock, _sftp = _mock_ssh_client(tarball)

    with patch.object(repo, "_sftp_connect", return_value=ssh_mock):
        repo.load_model("m", "v1", tmp_path / "extract")

    assert (tmp_path / "cache" / "m-v1.tar.gz").exists()


def test_sftp_save_model_uploads_and_renames(tmp_path: Path) -> None:
    repo = _sftp_repo(tmp_path / "cache")

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "m_v1").mkdir()
    (source_dir / "m_v1" / "model.pkl").write_bytes(b"data")

    ssh_mock = MagicMock()
    sftp_mock = MagicMock()
    ssh_mock.open_sftp.return_value.__enter__ = MagicMock(return_value=sftp_mock)
    ssh_mock.open_sftp.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(repo, "_sftp_connect", return_value=ssh_mock):
        location = repo.save_model("m", "v1", source_dir)

    sftp_mock.put.assert_called_once()
    sftp_mock.rename.assert_called_once_with(
        "/models/m_v1.tar.gz.tmp",
        "/models/m_v1.tar.gz",
    )
    assert location == "/models/m_v1.tar.gz"


def test_sftp_auth_password_env_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFTP_PASS", "my-secret")

    config = UrlModelSourceConfig(
        type="url",
        location=SftpModelLocation(
            scheme="sftp",
            host="sftp.example.com",
            username="user",
            remote_path="/models/m_v1.tar.gz",
            auth=SftpPasswordAuth(password=EnvRef(env="SFTP_PASS")),
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    with patch("app.repositories.url_repository.paramiko") as mock_paramiko:
        mock_ssh = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_ssh
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        repo._sftp_connect(config.location)  # type: ignore[arg-type]

    connect_kwargs = mock_ssh.connect.call_args[1]
    assert connect_kwargs["password"] == "my-secret"


def test_sftp_key_auth_env_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SFTP_KEY_PATH", "/home/user/.ssh/id_rsa")

    config = UrlModelSourceConfig(
        type="url",
        location=SftpModelLocation(
            scheme="sftp",
            host="sftp.example.com",
            username="user",
            remote_path="/models/m_v1.tar.gz",
            auth=SftpKeyAuth(private_key_path=EnvRef(env="SFTP_KEY_PATH")),
        ),
    )
    repo = UrlModelRepository(cache_dir=tmp_path / "cache", source_config=config)

    with patch("app.repositories.url_repository.paramiko") as mock_paramiko:
        mock_ssh = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_ssh
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()
        repo._sftp_connect(config.location)  # type: ignore[arg-type]

    connect_kwargs = mock_ssh.connect.call_args[1]
    assert connect_kwargs["key_filename"] == "/home/user/.ssh/id_rsa"
