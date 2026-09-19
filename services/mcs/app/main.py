import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .routers import health
from .routers import batches
from .routers import devices
from .services import mark_offline_devices


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "[%(levelname)s] "
        "%(name)s - "
        "%(message)s"
    ),
)


async def offline_device_monitor():
    while True:
        await asyncio.sleep(
            settings.device_health_check_interval_seconds
        )
        await mark_offline_devices()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    monitor_task = asyncio.create_task(
        offline_device_monitor()
    )
    try:
        yield
    finally:
        monitor_task.cancel()
        await asyncio.gather(
            monitor_task,
            return_exceptions=True,
        )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


app.include_router(
    devices.router
)

app.include_router(
    health.router
)

app.include_router(
    batches.router
)


@app.get("/")
async def root():

    return {
        "service": "Main Control Service",
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def service_health():

    return {
        "service": "mcs",
        "status": "healthy",
    }