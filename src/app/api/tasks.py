import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import RequeueTaskResponse, TaskResponse, TaskResultPhoto, TaskResultsResponse
from app.db.models import Task, TaskStatus
from app.db.session import get_db
from app.worker.queue import enqueue_processing_task

router = APIRouter(prefix="/tasks", tags=["Tasks"])

REQUEUEABLE_STATUSES = {TaskStatus.PENDING, TaskStatus.NEEDS_RETRY}


@router.get("/{task_id}")
def get_task(task_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> TaskResponse:
    """
    Return task status and linked photo identifiers.

    Raises:
        HTTPException: If the task does not exist.
    """
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return TaskResponse(
        id=task.id,
        status=task.status,
        image_count=task.image_count,
        attempts=task.attempts,
        max_attempts=task.max_attempts,
        last_error=task.last_error,
        started_at=task.started_at,
        finished_at=task.finished_at,
        photo_ids=[photo.id for photo in task.photos],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/{task_id}/results")
def get_task_results(task_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> TaskResultsResponse:
    """
    Return detection results for a completed task.

    Raises:
        HTTPException: If the task does not exist or is not completed yet.
    """
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Task is not completed yet: {task.status}",
        )

    return TaskResultsResponse(
        task_id=task.id,
        status=task.status,
        photos=[
            TaskResultPhoto(
                photo_id=photo.id,
                original_filename=photo.original_filename,
                width=photo.width,
                height=photo.height,
                detections=photo.detections or [],
                preview_url=f"/photos/{photo.id}/preview" if photo.preview_storage_key is not None else None,
            )
            for photo in task.photos
        ],
    )


@router.post("/{task_id}/requeue")
def requeue_task(task_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> RequeueTaskResponse:
    """
    Put a pending task back into the worker queue.

    Raises:
        HTTPException: If the task does not exist or cannot be requeued.
    """
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status not in REQUEUEABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task cannot be requeued from status: {task.status}",
        )

    task.status = TaskStatus.QUEUED
    db.commit()
    enqueue_processing_task(task.id)

    return RequeueTaskResponse(task_id=task.id, status=task.status, queued=True)
