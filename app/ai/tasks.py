import uuid
from app.celery_app import celery_app
from app.database import SessionLocal
from app.ai.vlm_client import get_vlm_client
from app.ai.embed_client import get_embedding_client
from app.storage import get_storage


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def celery_process_asset(self, asset_id: str, stages: list, job_id: str = None):
    """Process a single asset through the AI pipeline.

    Creates its own DB session (separate from web process).
    Retries up to 3 times on failure.
    """
    from app.assets.models import Asset, ProcessingJob, JobStatus

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
            job = db.get(ProcessingJob, uuid.UUID(job_id))
            if job:
                job.processed += 1
                db.commit()

    except Exception as exc:
        if job_id:
            try:
                job = db.get(ProcessingJob, uuid.UUID(job_id))
                if job:
                    job.failed_count += 1
                    db.commit()
            except Exception:
                pass
        db.rollback()
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
    finally:
        db.close()

    for asset_id in asset_ids:
        celery_process_asset.delay(asset_id, stages, job_id)
