import uuid
from datetime import datetime, timezone
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

    completed = min(job.total, max(0, job.processed + job.failed_count))
    remaining = max(0, job.total - completed)
    if job.total > 0:
        progress_pct = round((completed / job.total) * 100, 2)
    else:
        progress_pct = 100.0 if str(job.status) in {"done", "failed"} else 0.0

    elapsed_seconds = None
    throughput_items_per_min = None
    eta_seconds = None

    if job.created_at:
        now = datetime.now(timezone.utc)
        created_at = job.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = max(0.0, (now - created_at).total_seconds())
        if elapsed_seconds > 0 and completed > 0:
            throughput_items_per_min = round((completed / elapsed_seconds) * 60, 2)
            items_per_second = completed / elapsed_seconds
            if items_per_second > 0 and remaining > 0:
                eta_seconds = int(remaining / items_per_second)

    return {
        "id": str(job.id),
        "status": job.status,
        "stages": job.stages,
        "total": job.total,
        "processed": job.processed,
        "failed_count": job.failed_count,
        "completed": completed,
        "remaining": remaining,
        "progress_pct": progress_pct,
        "elapsed_seconds": int(elapsed_seconds) if elapsed_seconds is not None else None,
        "throughput_items_per_min": throughput_items_per_min,
        "eta_seconds": eta_seconds,
    }
