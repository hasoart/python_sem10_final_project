from fastapi import FastAPI

from app.api.photos import router as photos_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.include_router(photos_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
