import uuid
from dataclasses import dataclass
from io import BytesIO

from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import ensure_bucket_exists, get_s3_client
from app.db.models import Photo, Task, TaskStatus
from app.worker.queue import enqueue_processing_task


@dataclass(frozen=True)
class PreparedPhoto:
    id: uuid.UUID
    original_filename: str
    mime_type: str
    content: bytes
    size_bytes: int
    width: int
    height: int
    storage_key: str


@dataclass(frozen=True)
class CreatedProcessingTask:
    task_id: uuid.UUID
    photo_ids: list[uuid.UUID]


def build_storage_key(upload_id: uuid.UUID, photo_id: uuid.UUID, filename: str) -> str:
    """Build object storage key for original photo."""
    safe_filename = filename.rsplit("/", maxsplit=1)[-1].rsplit("\\", maxsplit=1)[-1]
    return f"photos/original/{upload_id}/{photo_id}/{safe_filename}"


async def prepare_photo(file: UploadFile) -> PreparedPhoto:
    """
    Read, validate, and prepare uploaded image metadata.

    Raises:
        HTTPException: If file is empty or is not a valid image.
    """
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")

    try:
        image = Image.open(BytesIO(content))
        width, height = image.size
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file") from exc

    photo_id = uuid.uuid4()
    filename = file.filename or "image"
    return PreparedPhoto(
        id=photo_id,
        original_filename=filename,
        mime_type=file.content_type,
        content=content,
        size_bytes=len(content),
        width=width,
        height=height,
        storage_key=build_storage_key(uuid.uuid4(), photo_id, filename),
    )


def upload_photos_to_storage(photos: list[PreparedPhoto]) -> None:
    """
    Upload prepared photos to object storage.

    Raises:
        HTTPException: If object storage upload fails.
    """
    try:
        ensure_bucket_exists()
        client = get_s3_client()
        for photo in photos:
            client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=photo.storage_key,
                Body=photo.content,
                ContentType=photo.mime_type,
            )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload image to storage",
        ) from exc


async def upload_photo(db: Session, file: UploadFile) -> Photo:
    """Store uploaded image and create photo row without processing task."""
    prepared_photo = await prepare_photo(file)
    upload_photos_to_storage([prepared_photo])

    photo = Photo(
        id=prepared_photo.id,
        task_id=None,
        original_filename=prepared_photo.original_filename,
        mime_type=prepared_photo.mime_type,
        size_bytes=prepared_photo.size_bytes,
        width=prepared_photo.width,
        height=prepared_photo.height,
        storage_key=prepared_photo.storage_key,
    )
    db.add(photo)
    db.commit()
    return photo


def create_processing_task(db: Session, photo_ids: list[uuid.UUID]) -> CreatedProcessingTask:
    """
    Create queued task from already uploaded photos.

    Raises:
        HTTPException: If photo ids are missing, unknown, or already linked to a task.
    """
    if not photo_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one photo is required")
    if len(set(photo_ids)) != len(photo_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photo ids must be unique")

    photos: list[Photo] = []
    for photo_id in photo_ids:
        photo = db.get(Photo, photo_id)
        if photo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo not found: {photo_id}")
        if photo.task_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Photo already linked to task: {photo_id}",
            )
        photos.append(photo)

    task_id = uuid.uuid4()
    task = Task(id=task_id, status=TaskStatus.QUEUED, image_count=len(photos))
    db.add(task)

    for photo in photos:
        photo.task_id = task_id

    db.commit()
    enqueue_processing_task(task_id)
    return CreatedProcessingTask(
        task_id=task.id,
        photo_ids=[photo.id for photo in photos],
    )
