from fastapi import APIRouter, HTTPException

from app.jobs.service import get_job_backend

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    backend = get_job_backend()
    try:
        return backend.get_status(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}") from exc
