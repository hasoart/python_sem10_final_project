from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.photos import router as photos_router
from app.api.tasks import router as tasks_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photos_router)
app.include_router(tasks_router)


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
