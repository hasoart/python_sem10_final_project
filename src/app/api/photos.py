import uuid
from collections.abc import Iterator
from io import BytesIO
from typing import Annotated, Protocol

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.api.schemas import PhotoResponse, UploadPhotoResponse
from app.core.config import settings
from app.core.storage import ensure_bucket_exists, get_s3_client
from app.db.models import Photo, Task, TaskStatus
from app.db.session import get_db
from app.worker.queue import enqueue_processing_task

router = APIRouter(prefix="/photos", tags=["Photos"])


class S3Body(Protocol):
    def iter_chunks(self) -> Iterator[bytes]:
        """Yield response body chunks."""
        ...

    def close(self) -> None:
        """Close response body."""
        ...


def _build_storage_key(task_id: uuid.UUID, photo_id: uuid.UUID, filename: str) -> str:
    safe_filename = filename.rsplit("/", maxsplit=1)[-1].rsplit("\\", maxsplit=1)[-1]
    return f"photos/original/{task_id}/{photo_id}/{safe_filename}"


def _iter_s3_body(body: S3Body) -> Iterator[bytes]:
    try:
        yield from body.iter_chunks()
    finally:
        body.close()


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
) -> UploadPhotoResponse:
    """
    Upload one image, store it in MinIO, and create a processing task.

    Raises:
        HTTPException: If the file is invalid or storage upload fails.
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

    task_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    storage_key = _build_storage_key(task_id, photo_id, file.filename or "image")

    try:
        ensure_bucket_exists()
        get_s3_client().put_object(
            Bucket=settings.s3_bucket_name,
            Key=storage_key,
            Body=content,
            ContentType=file.content_type,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload image to storage",
        ) from exc

    task = Task(id=task_id, status=TaskStatus.QUEUED, image_count=1)
    photo = Photo(
        id=photo_id,
        task_id=task_id,
        original_filename=file.filename or "image",
        mime_type=file.content_type,
        size_bytes=len(content),
        width=width,
        height=height,
        storage_key=storage_key,
    )
    db.add(task)
    db.add(photo)
    db.commit()

    enqueue_processing_task(task_id)

    return UploadPhotoResponse(task_id=task_id, photo_id=photo_id)


@router.get("/{photo_id}")
def get_photo(photo_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> PhotoResponse:
    """
    Return photo metadata and stored detection results.

    Raises:
        HTTPException: If the photo does not exist.
    """
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    return PhotoResponse(
        id=photo.id,
        task_id=photo.task_id,
        original_filename=photo.original_filename,
        mime_type=photo.mime_type,
        size_bytes=photo.size_bytes,
        width=photo.width,
        height=photo.height,
        storage_key=photo.storage_key,
        preview_storage_key=photo.preview_storage_key,
        status=photo.status,
        error=photo.error,
        detections=photo.detections,
        created_at=photo.created_at,
        updated_at=photo.updated_at,
    )


@router.get("/{photo_id}/file")
def get_photo_file(photo_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> StreamingResponse:
    """
    Stream the original image from MinIO.

    Raises:
        HTTPException: If the photo or stored image does not exist.
    """
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    try:
        response = get_s3_client().get_object(Bucket=settings.s3_bucket_name, Key=photo.storage_key)
    except ClientError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored image not found") from exc

    return StreamingResponse(
        _iter_s3_body(response["Body"]),
        media_type=photo.mime_type,
        headers={"Content-Disposition": f'inline; filename="{photo.original_filename}"'},
    )


@router.get("/{photo_id}/preview")
def get_photo_preview(photo_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> StreamingResponse:
    """
    Stream the annotated preview image from MinIO.

    Raises:
        HTTPException: If the photo or preview does not exist.
    """
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.preview_storage_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found")

    try:
        response = get_s3_client().get_object(Bucket=settings.s3_bucket_name, Key=photo.preview_storage_key)
    except ClientError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored preview not found") from exc

    return StreamingResponse(
        _iter_s3_body(response["Body"]),
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="preview-{photo.original_filename}"'},
    )
