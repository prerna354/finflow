from celery import Celery

from app.core.config import settings

celery_app = Celery("finflow", broker=settings.REDIS_URL, include=["app.workers.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,
    task_ignore_result=True,
)
