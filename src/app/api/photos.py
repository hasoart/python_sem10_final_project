import uuid
from collections.abc import Iterator
from typing import Annotated, Protocol

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.schemas import PhotoResponse, UploadPhotoResponse
from app.core.config import settings
from app.core.storage import get_s3_client
from app.db.models import Photo
from app.db.session import get_db
from app.services.uploads import upload_photo as upload_photo_service

router = APIRouter(prefix="/photos", tags=["Photos"])


class S3Body(Protocol):
    def iter_chunks(self) -> Iterator[bytes]:
        """Yield response body chunks."""
        ...

    def close(self) -> None:
        """Close response body."""
        ...


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
    """Upload one image to MinIO without starting processing."""
    photo = await upload_photo_service(db, file)
    return UploadPhotoResponse(photo_id=photo.id)


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
