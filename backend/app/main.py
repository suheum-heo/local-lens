"""LocalLens FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import photos, search
from app.config import settings

app = FastAPI(
    title="LocalLens API",
    description="Discover restaurants in South Korea via Kakao + Google signals.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(photos.router, prefix="/api", tags=["photos"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "provider_mode": settings.provider_mode}
