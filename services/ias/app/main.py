import logging

from fastapi import FastAPI

from .config import settings
from .model_manager import model_manager
from .routers import analysis


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "[%(levelname)s] "
        "%(name)s - "
        "%(message)s"
    ),
)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


app.include_router(
    analysis.router
)


@app.on_event("startup")
async def startup():

    logging.getLogger("ias").info(
        "Starting Image Analysis Service..."
    )

    model_manager.load()


@app.get("/")
async def root():

    return {
        "service": "Image Analysis Service",
        "version": settings.app_version,
        "model_loaded": model_manager.is_loaded,
    }


@app.get("/health")
async def health():

    if model_manager.is_loaded:

        return {
            "service": "ias",
            "status": "healthy",
            "model_loaded": True,
            "model_id": settings.model_id,
            "model_version": settings.model_version,
        }

    return {
        "service": "ias",
        "status": "degraded",
        "model_loaded": False,
        "model_id": settings.model_id,
        "model_version": settings.model_version,
    }