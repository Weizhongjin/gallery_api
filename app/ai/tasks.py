import uuid
from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.ai.vlm_client import get_vlm_client
from app.ai.embed_client import get_embedding_client
from app.storage import get_storage


def _update_job_progress(db, job_uuid: uuid.UUID, processed_inc: int = 0, failed_inc: int = 0) -> None:
    from app.assets.models import ProcessingJob, JobStatus

    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.id == job_uuid)
        .with_for_update()
        .first()
    )
    if not job:
        return

    if processed_inc:
        job.processed += processed_inc
    if failed_inc:
        job.failed_count += failed_inc

    if job.status == JobStatus.running and (job.processed + job.failed_count >= job.total):
        if job.total > 0 and job.failed_count >= job.total:
            job.status = JobStatus.failed
        else:
            job.status = JobStatus.done


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def celery_process_asset(self, asset_id: str, stages: list, job_id: str = None):
    """Process a single asset through the AI pipeline.

    Creates its own DB session (separate from web process).
    Retries up to 3 times on failure.
    """
    from app.assets.models import Asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, uuid.UUID(asset_id))
        if not asset:
            return

        storage = get_storage()

        if "classify" in stages:
            from app.ai.processing import classify_asset
            classify_asset(db, asset, get_vlm_client(), storage)
            db.commit()

        if "embed" in stages:
            from app.ai.processing import embed_asset
            embed_asset(db, asset, get_embedding_client(), storage)
            db.commit()

        if job_id:
            _update_job_progress(db, uuid.UUID(job_id), processed_inc=1)
            db.commit()

    except Exception as exc:
        db.rollback()
        if job_id and self.request.retries >= self.max_retries:
            _update_job_progress(db, uuid.UUID(job_id), failed_inc=1)
            db.commit()
            raise
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task
def celery_run_reprocess_job(job_id: str, stages: list):
    """Dispatch one celery_process_asset task per asset."""
    from app.assets.models import Asset, ProcessingJob, JobStatus

    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, uuid.UUID(job_id))
        if job:
            job.status = JobStatus.running
            db.commit()
        asset_ids = [str(row.id) for row in db.query(Asset.id).all()]
        if not asset_ids and job:
            job.status = JobStatus.done
            db.commit()
    finally:
        db.close()

    for asset_id in asset_ids:
        celery_process_asset.delay(asset_id, stages, job_id)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def celery_ingest_storage_batch(self, job_id: str, keys: list[str], prefix: str, stages: list[str]):
    from app.assets.models import JobStatus, ProcessingJob
    from app.assets.service import _ingest_storage_batch

    db = SessionLocal()
    try:
        _ingest_storage_batch(db, uuid.UUID(job_id), keys, prefix, stages)
        db.commit()
    except Exception as exc:
        db.rollback()
        if self.request.retries >= self.max_retries:
            job = db.get(ProcessingJob, uuid.UUID(job_id))
            if job:
                job.status = JobStatus.failed
                db.commit()
            raise
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=settings.aigc_soft_timeout_seconds,
    time_limit=settings.aigc_hard_timeout_seconds,
)
def celery_aigc_generate(self, task_id: str):
    """Run AIGC image generation for a queued task.

    Uses its own DB session (separate from web process).
    Respects soft/hard timeouts from config (default 900s/1200s).
    """
    from app.aigc.service import run_aigc_generation, mark_aigc_task_failed

    db = SessionLocal()
    try:
        run_aigc_generation(db, uuid.UUID(task_id))
        db.commit()
    except Exception:
        db.rollback()
        try:
            mark_aigc_task_failed(db, uuid.UUID(task_id), error_code="GENERATION_FAILED")
            db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()
