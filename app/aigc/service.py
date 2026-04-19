import uuid

from sqlalchemy.orm import Session

from app.aigc.models import AigcTask, AigcTaskCandidate, AigcTaskStatus
from app.config import settings
from app.aigc.provider_registry import get_provider


def mark_aigc_task_failed(db: Session, task_id: uuid.UUID, error_code: str) -> None:
    task = db.get(AigcTask, task_id)
    if task:
        task.status = AigcTaskStatus.failed
        task.error_code = error_code


def run_aigc_generation(db: Session, task_id: uuid.UUID) -> None:
    task = db.get(AigcTask, task_id)
    if not task:
        return

    task.status = AigcTaskStatus.running

    provider = get_provider(task.provider, settings)
    images = provider.generate(
        prompt="virtual try-on",
        image_data_urls=[],
        resolution="2K",
    )

    for idx, img_bytes in enumerate(images):
        candidate = AigcTaskCandidate(
            task_id=task.id,
            seq_no=idx + 1,
        )
        db.add(candidate)

    task.status = AigcTaskStatus.review_pending
