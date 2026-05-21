import uuid
from datetime import UTC, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from sqlalchemy.orm import Session
from ultralytics import YOLO

from app.core.config import settings
from app.core.storage import get_s3_client
from app.db.models import Photo, PhotoStatus, Task, TaskStatus
from app.db.session import SessionLocal
from app.worker.celery_app import celery_app


@lru_cache
def get_model() -> YOLO:
    """Load YOLO model once per worker process."""
    return YOLO(settings.yolo_model_path)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _download_photo(photo: Photo) -> bytes:
    response = get_s3_client().get_object(Bucket=settings.s3_bucket_name, Key=photo.storage_key)
    body = response["Body"]
    try:
        return body.read()
    finally:
        body.close()


def _preview_key(photo: Photo) -> str:
    stem = Path(photo.original_filename).stem or "image"
    return f"photos/preview/{photo.task_id}/{photo.id}/{stem}.jpg"


def _detect_objects(content: bytes) -> tuple[list[dict[str, Any]], bytes]:
    image = Image.open(BytesIO(content)).convert("RGB")
    result = get_model().predict(image, conf=settings.yolo_confidence, verbose=False)[0]

    detections: list[dict[str, Any]] = []
    draw = ImageDraw.Draw(image)

    for box in result.boxes:
        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
        confidence = float(box.conf[0])
        class_id = int(box.cls[0])
        class_name = result.names[class_id]

        detections.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "confidence": confidence,
                "bbox": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                },
            },
        )

        label = f"{class_name} {confidence:.2f}"
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        draw.text((x1, max(0, y1 - 12)), label, fill="red")

    preview = BytesIO()
    image.save(preview, format="JPEG", quality=90)
    return detections, preview.getvalue()


def _process_photo(db: Session, photo: Photo) -> None:
    photo.status = PhotoStatus.PROCESSING
    db.commit()

    content = _download_photo(photo)
    detections, preview_content = _detect_objects(content)
    preview_key = _preview_key(photo)

    get_s3_client().put_object(
        Bucket=settings.s3_bucket_name,
        Key=preview_key,
        Body=preview_content,
        ContentType="image/jpeg",
    )

    photo.detections = detections
    photo.preview_storage_key = preview_key
    photo.status = PhotoStatus.COMPLETED
    photo.error = None
    db.commit()


@celery_app.task(name="process_task")
def process_task(task_id: str) -> None:
    """Process all photos linked to one task."""
    db = SessionLocal()
    try:
        task_uuid = uuid.UUID(task_id)
        task = db.get(Task, task_uuid)
        if task is None:
            return
        if task.status not in {TaskStatus.QUEUED, TaskStatus.PROCESSING}:
            return

        task.status = TaskStatus.PROCESSING
        task.started_at = task.started_at or _now()
        task.attempts += 1
        task.last_error = None
        db.commit()

        for photo in task.photos:
            _process_photo(db, photo)

        task.status = TaskStatus.COMPLETED
        task.finished_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        task = db.get(Task, uuid.UUID(task_id))
        if task is not None:
            task.status = TaskStatus.FAILED if task.attempts >= task.max_attempts else TaskStatus.NEEDS_RETRY
            task.last_error = str(exc)
            task.finished_at = _now()
            for photo in task.photos:
                if photo.status != PhotoStatus.COMPLETED:
                    photo.status = PhotoStatus.FAILED
                    photo.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()
