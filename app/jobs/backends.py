from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from redis import Redis
from rq import Queue


class JobBackend(ABC):
    """Abstract interface for queuing jobs and reading their status."""

    @abstractmethod
    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        """Queue a task and return the generated job id."""
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> dict[str, Any]:
        """Return backend-specific status details for a job id."""
        raise NotImplementedError


class InMemoryJobBackend(JobBackend):
    """In-process backend used for local synchronous development flows."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, Any]] = {}

    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        """Store queued job metadata in memory and return the job id."""
        job_id = f"mem-{uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "task": task_name,
            "payload": payload,
            "created_at": now,
            "updated_at": now,
        }
        return job_id

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Return status for an in-memory job id."""
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]


class RedisRQBackend(JobBackend):
    """RQ/Redis job backend used for asynchronous worker execution."""

    def __init__(self, redis_url: str, handler_map: dict[str, str]) -> None:
        self.redis = Redis.from_url(redis_url)
        self.queue = Queue("tsaas", connection=self.redis)
        self.handler_map = handler_map

    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        """Enqueue a task in RQ and return the corresponding job id."""
        if task_name not in self.handler_map:
            raise ValueError(f"No handler configured for task {task_name}")
        job = self.queue.enqueue(self.handler_map[task_name], payload)
        return str(job.id)

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Fetch and normalize RQ job status details."""
        job = self.queue.fetch_job(job_id)
        if job is None:
            raise KeyError(job_id)

        status = job.get_status() or "unknown"
        created_at = job.created_at.isoformat() if job.created_at else None
        updated_at = job.ended_at.isoformat() if job.ended_at else created_at

        detail: dict[str, Any] = {}
        if job.result is not None:
            detail["result"] = job.result
        if job.exc_info:
            detail["error"] = job.exc_info

        return {
            "job_id": job_id,
            "status": status,
            "task": str(job.func_name),
            "created_at": created_at,
            "updated_at": updated_at,
            "detail": detail,
        }
