import uuid
from collections.abc import AsyncGenerator
from io import BytesIO

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.db.session import get_db
from app.main import app
from tests.fakes import FakeDb, FakeS3Client


@pytest.fixture
def fake_db() -> FakeDb:
    return FakeDb()


@pytest.fixture
def fake_s3() -> FakeS3Client:
    return FakeS3Client()


@pytest.fixture
def queued_task_ids() -> list[uuid.UUID]:
    return []


@pytest_asyncio.fixture
async def client(
    fake_db: FakeDb,
    fake_s3: FakeS3Client,
    queued_task_ids: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[FakeDb, None]:
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr("app.services.uploads.ensure_bucket_exists", lambda: None)
    monkeypatch.setattr("app.services.uploads.get_s3_client", lambda: fake_s3)
    monkeypatch.setattr("app.services.uploads.enqueue_processing_task", queued_task_ids.append)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.fixture
def image_bytes() -> bytes:
    image = Image.new("RGB", (32, 24), color="white")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()
