from celery import Celery
from kombu import Queue
from app.config import settings

celery_app = Celery(
    "cloth_gallery",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.ai.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.celery_default_queue,
    task_default_routing_key=settings.celery_default_queue,
    task_queues=(
        Queue(
            settings.celery_default_queue,
            routing_key=settings.celery_default_queue,
        ),
        Queue(
            settings.celery_aigc_queue,
            routing_key=settings.celery_aigc_queue,
        ),
    ),
    task_routes={
        "app.ai.tasks.celery_aigc_generate": {
            "queue": settings.celery_aigc_queue,
            "routing_key": settings.celery_aigc_queue,
        },
    },
)
