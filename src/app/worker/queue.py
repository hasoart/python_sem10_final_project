import uuid

from app.worker.celery_app import celery_app


def enqueue_processing_task(task_id: uuid.UUID) -> None:
    """Send task processing message to the worker queue."""
    celery_app.send_task("process_task", args=[str(task_id)])
