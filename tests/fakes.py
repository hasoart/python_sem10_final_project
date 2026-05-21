import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.db.models import Photo, PhotoStatus, Task, TaskStatus


class FakeS3Body:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def iter_chunks(self) -> Iterator[bytes]:
        yield self.content

    def close(self) -> None:
        pass


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:  # noqa: N803
        self.objects[Bucket, Key] = {
            "body": Body,
            "content_type": ContentType,
        }

    def get_object(self, Bucket: str, Key: str) -> dict[str, FakeS3Body]:  # noqa: N803
        return {"Body": FakeS3Body(self.objects[Bucket, Key]["body"])}


class FakeDb:
    def __init__(self) -> None:
        self.tasks: dict[uuid.UUID, Task] = {}
        self.photos: dict[uuid.UUID, Photo] = {}
        self.commits = 0

    def add(self, obj: object) -> None:
        now = datetime.now(tz=UTC)
        if isinstance(obj, Task):
            obj.status = obj.status or TaskStatus.PENDING
            obj.created_at = obj.created_at or now
            obj.updated_at = obj.updated_at or now
            self.tasks[obj.id] = obj
        if isinstance(obj, Photo):
            obj.status = obj.status or PhotoStatus.PENDING
            obj.created_at = obj.created_at or now
            obj.updated_at = obj.updated_at or now
            self.photos[obj.id] = obj

    def get(self, model: type[Task] | type[Photo], object_id: uuid.UUID) -> Task | Photo | None:
        if model is Task:
            return self.tasks.get(object_id)
        if model is Photo:
            return self.photos.get(object_id)
        return None

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        pass
