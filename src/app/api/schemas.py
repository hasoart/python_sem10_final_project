import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models import JSONValue, PhotoStatus, TaskStatus


class UploadPhotoResponse(BaseModel):
    photo_id: uuid.UUID


class CreateTaskResponse(BaseModel):
    task_id: uuid.UUID
    photo_ids: list[uuid.UUID]


class CreateTaskRequest(BaseModel):
    photo_ids: list[uuid.UUID]


class PhotoResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
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


class TaskResponse(BaseModel):
    id: uuid.UUID
    status: TaskStatus
    image_count: int
    attempts: int
    max_attempts: int
    last_error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    photo_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class TaskResultPhoto(BaseModel):
    photo_id: uuid.UUID
    original_filename: str
    width: int | None
    height: int | None
    detections: list[dict[str, JSONValue]]
    preview_url: str | None


class TaskResultsResponse(BaseModel):
    task_id: uuid.UUID
    status: TaskStatus
    photos: list[TaskResultPhoto]


class RequeueTaskResponse(BaseModel):
    task_id: uuid.UUID
    status: TaskStatus
    queued: bool
