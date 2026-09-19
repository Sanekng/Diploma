import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ============================================================
# Configuration
# ============================================================

MCS_URL = os.getenv(
    "MCS_URL",
    "http://mcs:8000",
).rstrip("/")

DBS_URL = os.getenv(
    "DBS_URL",
    "http://dbs:8002",
).rstrip("/")


BASE_DIR = Path(
    __file__
).resolve().parent.parent

GEOJSON_DIR = BASE_DIR / "geojson"


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,

    format=(
        "%(asctime)s "
        "[%(levelname)s] "
        "%(name)s - "
        "%(message)s"
    ),
)

logger = logging.getLogger("wds")


# ============================================================
# Application
# ============================================================

app = FastAPI(
    title="Fire Detection Web Dashboard",
    version="0.1.0",
)


app.mount(
    "/static",
    StaticFiles(
        directory=str(
            BASE_DIR / "static"
        )
    ),
    name="static",
)


app.mount(
    "/geojson",
    StaticFiles(
        directory=str(
            GEOJSON_DIR
        )
    ),
    name="geojson",
)

STORAGE_DIR = Path(
    os.getenv(
        "STORAGE_PATH",
        "/app/storage",
    )
)

STORAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

app.mount(
    "/storage",
    StaticFiles(
        directory=str(
            STORAGE_DIR
        )
    ),
    name="storage",
)


templates = Jinja2Templates(
    directory=str(
        BASE_DIR / "templates"
    )
)


# ============================================================
# HTTP helper
# ============================================================

async def get_json(
    url: str,
    default: Any,
):
    """
    Safely request JSON from another
    internal microservice.

    WDS must remain usable even if another
    service temporarily becomes unavailable.
    """

    try:

        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:

            response = await client.get(
                url
            )

            response.raise_for_status()

            return response.json()

    except Exception as exc:

        logger.warning(
            "Request failed: %s - %s",
            url,
            exc,
        )

        return default


# ============================================================
# Pages
# ============================================================

@app.get("/")
async def dashboard(
    request: Request,
):

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "title": (
                "Fire Detection Dashboard"
            ),
        },
    )


# ============================================================
# API
# ============================================================

@app.get(
    "/api/dashboard"
)
async def dashboard_data():

    devices = await get_json(
        f"{DBS_URL}/api/v1/devices",
        {
            "devices": []
        },
    )

    batches = await get_json(
        f"{DBS_URL}/api/v1/batches?limit=50",
        {
            "batches": []
        },
    )

    logs = await get_json(
        f"{DBS_URL}/api/v1/logs?limit=50",
        {
            "logs": []
        },
    )

    return {
        "devices": devices.get(
            "devices",
            []
        ),

        "batches": batches.get(
            "batches",
            []
        ),

        "logs": logs.get(
            "logs",
            []
        ),
    }


@app.get(
    "/api/devices/{device_id}"
)
async def device_details(
    device_id: str,
):

    device = await get_json(
        (
            f"{DBS_URL}/api/v1/devices/"
            f"{device_id}"
        ),
        None,
    )

    if device is None:

        return JSONResponse(
            status_code=404,
            content={
                "detail":
                    "Device not found."
            },
        )

    batches = await get_json(
        (
            f"{DBS_URL}/api/v1/batches/"
            f"device/{device_id}?limit=3"
        ),
        {
            "batches": []
        },
    )

    logs = await get_json(
        (
            f"{DBS_URL}/api/v1/logs"
            f"?device_id={device_id}"
            f"&limit=20"
        ),
        {
            "logs": []
        },
    )

    return {
        "device": device,

        "batches": batches.get(
            "batches",
            []
        ),

        "logs": logs.get(
            "logs",
            []
        ),
    }


# ============================================================
# GeoJSON
# ============================================================

@app.get(
    "/api/map/geojson"
)
async def map_geojson():

    geojson_file = (
        GEOJSON_DIR
        / "montenegro.geojson"
    )

    if not geojson_file.exists():

        return {
            "type": "FeatureCollection",
            "features": [],
        }

    try:

        with open(
            geojson_file,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception as exc:

        logger.error(
            "Could not read Montenegro "
            "GeoJSON: %s",
            exc,
        )

        return JSONResponse(
            status_code=500,
            content={
                "detail":
                    "Invalid GeoJSON file."
            },
        )


@app.post(
    "/api/v1/events/device"
)
async def device_event(
    event: Dict[str, Any],
):

    logger.info(
        "Device event received: device=%s",
        event.get("device_id"),
    )

    return {
        "success": True,
        "event": "device",
    }


@app.post(
    "/api/v1/events/batch"
)
async def batch_event(
    event: Dict[str, Any],
):

    logger.info(
        "Batch event received: batch=%s status=%s",
        event.get("batch_id"),
        event.get("status"),
    )

    return {
        "success": True,
        "event": "batch",
    }


# ============================================================
# Health
# ============================================================

@app.get(
    "/health"
)
async def health():

    dbs_health = await get_json(
        f"{DBS_URL}/health",
        None,
    )

    mcs_health = await get_json(
        f"{MCS_URL}/health",
        None,
    )

    return {
        "service": "wds",

        "status": "healthy",

        "dbs": (
            "healthy"
            if dbs_health
            else "unavailable"
        ),

        "mcs": (
            "healthy"
            if mcs_health
            else "unavailable"
        ),
    }