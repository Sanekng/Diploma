import logging

from fastapi import FastAPI

from .config import settings
from .database import (
    initialize_database,
    ping_database,
)
from .routers import (
    logs,
)
from .routers import batches
from .routers import devices


logging.basicConfig(
    level=logging.INFO,

    format=(
        "%(asctime)s "
        "[%(levelname)s] "
        "%(name)s - "
        "%(message)s"
    ),
)


logger = logging.getLogger(
    "dbs"
)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


app.include_router(
    devices.router
)

app.include_router(
    batches.router
)

app.include_router(
    logs.router
)


@app.on_event("startup")
async def startup():

    logger.info(
        "Starting Database Service..."
    )

    initialize_database()


@app.get("/")
async def root():

    return {
        "service": "Database Service",
        "version": settings.app_version,
    }


@app.get("/health")
async def health():

    mongodb_healthy = (
        ping_database()
    )

    if mongodb_healthy:

        return {
            "service": "dbs",
            "status": "healthy",
            "mongodb": "healthy",
        }

    return {
        "service": "dbs",
        "status": "degraded",
        "mongodb": "unhealthy",
    }