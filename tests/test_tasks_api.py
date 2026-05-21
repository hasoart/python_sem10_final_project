import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm.attributes import set_committed_value

from app.api.tasks import get_task_results, requeue_task
from app.db.models import Photo, Task, TaskStatus
from tests.fakes import FakeDb


def test_get_task_results_returns_202_for_pending_task(fake_db: FakeDb) -> None:
    task = Task(id=uuid.uuid4(), image_count=1)
    fake_db.add(task)

    with pytest.raises(HTTPException) as exc_info:
        get_task_results(task.id, fake_db)

    assert exc_info.value.status_code == 202
    assert exc_info.value.detail == "Task is not completed yet: pending"


def test_get_task_results_returns_detection_json(fake_db: FakeDb) -> None:
    now = datetime.now(tz=UTC)
    task = Task(id=uuid.uuid4(), status=TaskStatus.COMPLETED, image_count=1)
    photo = Photo(
        id=uuid.uuid4(),
        task_id=task.id,
        original_filename="sample.jpg",
        mime_type="image/jpeg",
        size_bytes=100,
        width=640,
        height=480,
        storage_key="photos/original/sample.jpg",
        preview_storage_key="photos/preview/sample.jpg",
        detections=[
            {
                "class_id": 0,
                "class_name": "person",
                "confidence": 0.91,
                "bbox": {"x1": 1.0, "y1": 2.0, "x2": 3.0, "y2": 4.0},
            },
        ],
    )
    task.created_at = now
    task.updated_at = now
    photo.created_at = now
    photo.updated_at = now
    set_committed_value(task, "photos", [photo])
    fake_db.add(task)
    fake_db.add(photo)

    response = get_task_results(task.id, fake_db)

    assert response.task_id == task.id
    assert response.status == TaskStatus.COMPLETED
    assert len(response.photos) == 1
    assert response.photos[0].photo_id == photo.id
    assert response.photos[0].detections == photo.detections
    assert response.photos[0].preview_url == f"/photos/{photo.id}/preview"


def test_requeue_pending_task_marks_task_as_queued(
    fake_db: FakeDb,
    queued_task_ids: list,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = Task(id=uuid.uuid4(), image_count=1)
    fake_db.add(task)
    monkeypatch.setattr("app.api.tasks.enqueue_processing_task", queued_task_ids.append)

    response = requeue_task(task.id, fake_db)

    assert response.task_id == task.id
    assert response.status == TaskStatus.QUEUED
    assert response.queued is True
    assert task.status == TaskStatus.QUEUED
    assert queued_task_ids == [task.id]


def test_requeue_queued_task_is_rejected(
    fake_db: FakeDb,
    queued_task_ids: list,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = Task(id=uuid.uuid4(), status=TaskStatus.QUEUED, image_count=1)
    fake_db.add(task)
    monkeypatch.setattr("app.api.tasks.enqueue_processing_task", queued_task_ids.append)

    with pytest.raises(HTTPException) as exc_info:
        requeue_task(task.id, fake_db)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Task cannot be requeued from status: queued"
    assert queued_task_ids == []
