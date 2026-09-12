from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.schemas.job import JobOut
from app.services.jobs import JobService

router = APIRouter(prefix="/jobs", dependencies=[Depends(get_current_user)])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    job = JobService.get(db, job_id)
    if not job:
        raise NotFoundError("Job introuvable")
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(type: str | None = None, status: str | None = None, db: Session = Depends(get_db)):
    return JobService.list(db, type=type, status=status)
