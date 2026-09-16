import hashlib
import io
import os
import tarfile
import tempfile
from pathlib import Path

import requests

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore[assignment]

from app.core.errors import SourceValidationError
from app.repositories.base import ModelRepository
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


def _resolve_secret(value: str | EnvRef) -> str:
    """Return the resolved secret string, reading from env if value is an EnvRef."""
    if isinstance(value, EnvRef):
        secret = os.environ.get(value.env)
        if secret is None:
            raise SourceValidationError(f"Environment variable '{value.env}' is not set")
        return secret
    return value


def _build_auth_headers(location: HttpModelLocation) -> dict[str, str]:
    headers = dict(location.headers)
    if isinstance(location.auth, HttpBearerAuth):
        headers["Authorization"] = f"Bearer {_resolve_secret(location.auth.token)}"
    return headers


def _build_requests_auth(location: HttpModelLocation) -> tuple[str, str] | None:
    if isinstance(location.auth, HttpBasicAuth):
        return (_resolve_secret(location.auth.username), _resolve_secret(location.auth.password))
    return None


def _verify_checksum(data: bytes, expected: str | None) -> None:
    if expected is None:
        return
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise SourceValidationError("Model artifact checksum mismatch")


def _extract_tarball(tarball_path: Path, target_dir: Path, model_id: str, version: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball_path, "r:gz") as tf:
        tf.extractall(target_dir, filter="data")
    return target_dir / f"{model_id}_{version}"


def _make_tarball_bytes(source_dir: Path, model_id: str, version: str) -> bytes:
    artifact_name = f"{model_id}_{version}"
    artifact_path = source_dir / artifact_name
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(artifact_path, arcname=artifact_name)
    return buf.getvalue()


class UrlModelRepository(ModelRepository):
    """Model repository backed by a remote URL (HTTP/HTTPS or SFTP) with local cache."""

    def __init__(self, cache_dir: Path, source_config: UrlModelSourceConfig) -> None:
        self.cache_dir = cache_dir
        self.source_config = source_config

    def _cache_file(self, model_id: str, version: str) -> Path:
        return self.cache_dir / f"{model_id}-{version}.tar.gz"

    # ------------------------------------------------------------------
    # HTTP transport
    # ------------------------------------------------------------------

    def _http_load(self, location: HttpModelLocation, model_id: str, version: str, target_dir: Path) -> Path:
        cache = self._cache_file(model_id, version)
        if not cache.exists():
            headers = _build_auth_headers(location)
            basic_auth = _build_requests_auth(location)
            try:
                resp = requests.get(
                    str(location.url),
                    headers=headers,
                    auth=basic_auth,
                    timeout=location.timeout_seconds,
                    stream=True,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise SourceValidationError(f"Failed to fetch model artifact: {exc}") from exc
            data = resp.content
            _verify_checksum(data, location.checksum_sha256)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        return _extract_tarball(cache, target_dir, model_id, version)

    def _http_save(self, location: HttpModelLocation, model_id: str, version: str, source_dir: Path) -> str:
        data = _make_tarball_bytes(source_dir, model_id, version)
        headers = _build_auth_headers(location)
        basic_auth = _build_requests_auth(location)
        try:
            resp = requests.request(
                location.upload_method,
                str(location.url),
                data=data,
                headers=headers,
                auth=basic_auth,
                timeout=location.timeout_seconds,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SourceValidationError(f"Failed to upload model artifact: {exc}") from exc
        return str(location.url)

    def _http_exists(self, location: HttpModelLocation, model_id: str, version: str) -> bool:
        if self._cache_file(model_id, version).exists():
            return True
        try:
            resp = requests.head(
                str(location.url),
                headers=_build_auth_headers(location),
                auth=_build_requests_auth(location),
                timeout=location.timeout_seconds,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    # SFTP transport
    # ------------------------------------------------------------------

    def _sftp_connect(self, location: SftpModelLocation) -> "paramiko.SSHClient":  # type: ignore[name-defined]
        if paramiko is None:
            raise RuntimeError("paramiko is required for SFTP model sources; install it with: pip install paramiko")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = {
            "hostname": location.host,
            "port": location.port,
            "username": location.username,
            "timeout": location.timeout_seconds,
        }
        if isinstance(location.auth, SftpPasswordAuth):
            connect_kwargs["password"] = _resolve_secret(location.auth.password)
        elif isinstance(location.auth, SftpKeyAuth):
            connect_kwargs["key_filename"] = _resolve_secret(location.auth.private_key_path)
        ssh.connect(**connect_kwargs)
        return ssh

    def _sftp_load(self, location: SftpModelLocation, model_id: str, version: str, target_dir: Path) -> Path:
        cache = self._cache_file(model_id, version)
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            ssh = self._sftp_connect(location)
            try:
                with ssh.open_sftp() as sftp:
                    sftp.get(location.remote_path, str(cache))
            finally:
                ssh.close()
            data = cache.read_bytes()
            _verify_checksum(data, location.checksum_sha256)
        return _extract_tarball(cache, target_dir, model_id, version)

    def _sftp_save(self, location: SftpModelLocation, model_id: str, version: str, source_dir: Path) -> str:
        artifact_name = f"{model_id}_{version}"
        artifact_path = source_dir / artifact_name
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_fh:
            tmp_path = tmp_fh.name
        try:
            with tarfile.open(tmp_path, "w:gz") as tf:
                tf.add(artifact_path, arcname=artifact_name)
            ssh = self._sftp_connect(location)
            try:
                with ssh.open_sftp() as sftp:
                    remote_tmp = location.remote_path + ".tmp"
                    sftp.put(tmp_path, remote_tmp)
                    sftp.rename(remote_tmp, location.remote_path)
            finally:
                ssh.close()
        finally:
            os.unlink(tmp_path)
        return location.remote_path

    def _sftp_exists(self, location: SftpModelLocation, model_id: str, version: str) -> bool:
        if self._cache_file(model_id, version).exists():
            return True
        ssh = self._sftp_connect(location)
        try:
            with ssh.open_sftp() as sftp:
                sftp.stat(location.remote_path)
            return True
        except FileNotFoundError:
            return False
        finally:
            ssh.close()

    # ------------------------------------------------------------------
    # ModelRepository interface
    # ------------------------------------------------------------------

    def save_model(self, model_id: str, version: str, source_dir: Path) -> str:
        """Upload source_dir/{model_id}_{version}/ as a tarball to the remote location."""
        location = self.source_config.location
        if isinstance(location, HttpModelLocation):
            return self._http_save(location, model_id, version, source_dir)
        if isinstance(location, SftpModelLocation):
            return self._sftp_save(location, model_id, version, source_dir)
        raise ValueError(f"Unsupported location type: {type(location)}")

    def load_model(self, model_id: str, version: str, target_dir: Path) -> Path:
        """Download tarball from remote and extract into target_dir."""
        location = self.source_config.location
        if isinstance(location, HttpModelLocation):
            return self._http_load(location, model_id, version, target_dir)
        if isinstance(location, SftpModelLocation):
            return self._sftp_load(location, model_id, version, target_dir)
        raise ValueError(f"Unsupported location type: {type(location)}")

    def model_exists(self, model_id: str, version: str) -> bool:
        """Return whether the artifact is available in cache or on the remote."""
        location = self.source_config.location
        if isinstance(location, HttpModelLocation):
            return self._http_exists(location, model_id, version)
        if isinstance(location, SftpModelLocation):
            return self._sftp_exists(location, model_id, version)
        raise ValueError(f"Unsupported location type: {type(location)}")
