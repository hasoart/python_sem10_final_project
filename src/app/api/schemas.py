import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models import JSONValue, PhotoStatus


class UploadPhotoResponse(BaseModel):
    task_id: uuid.UUID
    photo_id: uuid.UUID


class PhotoResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    storage_key: str
    preview_storage_key: str | None
    status: PhotoStatus
    error: str | None
    detections: list[dict[str, JSONValue]] | None
    created_at: datetime
    updated_at: datetime
