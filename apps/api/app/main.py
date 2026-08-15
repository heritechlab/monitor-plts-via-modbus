from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.bms import router as bms_router
from app.api.v1.devices import router as devices_router
from app.api.v1.ingest import router as ingest_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    if settings.auto_bootstrap_device and settings.device_api_key:
        from app.cli import ensure_device

        await ensure_device(settings.device_slug, settings.device_name, settings.device_api_key)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(bms_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"name": settings.app_name, "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health() -> dict:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "time": datetime.now(UTC)}
