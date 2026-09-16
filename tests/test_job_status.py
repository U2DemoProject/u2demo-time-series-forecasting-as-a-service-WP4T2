"""Tests for normalized job status reporting across backends."""

import pytest

from app.jobs.backends import InMemoryJobBackend, RedisRQBackend
from app.schemas.common import JobStatus


class _FakeJob:
    """Minimal stand-in for an rq.job.Job used by RedisRQBackend.get_status."""

    def __init__(
        self,
        rq_status: str,
        args: tuple,
        result: object = None,
        exc_info: str | None = None,
    ) -> None:
        self._rq_status = rq_status
        self.args = args
        self.result = result
        self.exc_info = exc_info
        self.func_name = "app.jobs.handlers.train_task"
        self.created_at = None
        self.ended_at = None

    def get_status(self) -> str:
        return self._rq_status


@pytest.mark.parametrize(
    ("rq_status", "expected"),
    [
        ("queued", "queued"),
        ("deferred", "queued"),
        ("scheduled", "queued"),
        ("started", "running"),
        ("finished", "succeeded"),
        ("failed", "failed"),
        ("stopped", "failed"),
        ("canceled", "failed"),
        ("something-weird", "queued"),
    ],
)
def test_rq_status_is_normalized(
    monkeypatch: pytest.MonkeyPatch, rq_status: str, expected: str
) -> None:
    backend = RedisRQBackend(redis_url="redis://localhost:6379/0", handler_map={})
    fake = _FakeJob(rq_status, args=({"model_id": "m1"},), result={"ok": True})
    monkeypatch.setattr(backend.queue, "fetch_job", lambda _job_id: fake)

    status = backend.get_status("job-1")

    assert status["status"] == expected
    assert status["model_id"] == "m1"
    # Response must satisfy the public JobStatus contract.
    JobStatus.model_validate(status)


def test_rq_status_missing_job_raises_keyerror(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = RedisRQBackend(redis_url="redis://localhost:6379/0", handler_map={})
    monkeypatch.setattr(backend.queue, "fetch_job", lambda _job_id: None)
    with pytest.raises(KeyError):
        backend.get_status("ghost")


def test_memory_backend_reports_normalized_queued_status() -> None:
    backend = InMemoryJobBackend()
    job_id = backend.enqueue("train", {"model_id": "m1", "request": {}})
    status = backend.get_status(job_id)
    assert status["status"] == "queued"
    assert status["model_id"] == "m1"
    JobStatus.model_validate(status)
