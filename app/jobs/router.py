import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.assets.models import ProcessingJob
from app.auth.deps import get_current_user
from app.database import get_db

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": str(job.id),
        "status": job.status,
        "stages": job.stages,
        "total": job.total,
        "processed": job.processed,
        "failed_count": job.failed_count,
    }
