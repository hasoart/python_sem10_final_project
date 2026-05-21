import uuid

import pytest
from httpx import AsyncClient

from app.api.photos import get_photo
from app.core.config import settings
from tests.fakes import FakeDb, FakeS3Client


@pytest.mark.asyncio
async def test_upload_photo_creates_photo_without_processing_task(
    client: AsyncClient,
    fake_db: FakeDb,
    fake_s3: FakeS3Client,
    queued_task_ids: list,
    image_bytes: bytes,
) -> None:
    response = await client.post(
        "/photos",
        files={"file": ("sample.jpg", image_bytes, "image/jpeg")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["photo_id"]

    photo = next(iter(fake_db.photos.values()))

    assert fake_db.tasks == {}
    assert queued_task_ids == []
    assert photo.task_id is None
    assert photo.original_filename == "sample.jpg"
    assert photo.width == 32
    assert photo.height == 24
    assert (settings.s3_bucket_name, photo.storage_key) in fake_s3.objects


@pytest.mark.asyncio
async def test_upload_photo_rejects_non_image(client: AsyncClient, queued_task_ids: list) -> None:
    response = await client.post(
        "/photos",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File must be an image"
    assert queued_task_ids == []


@pytest.mark.asyncio
async def test_get_photo_returns_metadata(
    client: AsyncClient,
    fake_db: FakeDb,
    image_bytes: bytes,
) -> None:
    upload_response = await client.post(
        "/photos",
        files={"file": ("sample.jpg", image_bytes, "image/jpeg")},
    )
    photo_id = uuid.UUID(upload_response.json()["photo_id"])

    response = get_photo(photo_id, fake_db)

    assert response.id == photo_id
    assert response.original_filename == "sample.jpg"
    assert response.width == 32
    assert response.height == 24
