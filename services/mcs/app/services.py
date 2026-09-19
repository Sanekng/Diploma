import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from .clients import dbs_client, ias_client, wds_client
from .config import settings
from .logger import log_event
from .models import BatchStatus
from .state import mark_stale_devices, update_device_health


def utc_now():
    return datetime.now(timezone.utc)


async def mark_offline_devices():
    for device in mark_stale_devices(
        settings.device_offline_after_seconds
    ):
        offline_health = {
            "device_id": device["device_id"],
            "status": "OFFLINE",
            "timestamp": utc_now(),
            "hostname": device.get("hostname"),
            "camera": device.get("camera"),
            "last_batch_id": device.get("last_batch_id"),
        }

        try:
            await dbs_client.save_health(offline_health)
        except Exception as exc:
            log_event(
                "warning",
                "OFFLINE_DB_FAILED",
                str(exc),
                device_id=device["device_id"],
            )

        try:
            await wds_client.device_updated(device)
        except Exception as exc:
            log_event(
                "warning",
                "OFFLINE_WDS_FAILED",
                str(exc),
                device_id=device["device_id"],
            )

        log_event(
            "warning",
            "DEVICE_OFFLINE",
            "Device heartbeat timeout exceeded",
            device_id=device["device_id"],
        )


async def register_device(
    data: Dict[str, Any],
):

    device = {
        "device_id": data["device_id"],
        "hostname": data["hostname"],
        "device_type": data["device_type"],
        "camera": data["camera"],
        "location": data.get("location"),
        "status": "ONLINE",
        "registered_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }

    # Persist through DBS.
    try:
        await dbs_client.register_device(device)
    except Exception as exc:
        log_event(
            "warning",
            "DBS_REGISTRATION_FAILED",
            str(exc),
            device_id=data["device_id"],
        )

    # Keep local state.
    update_device_health(
        data["device_id"],
        {
            "device_id": data["device_id"],
            "hostname": data["hostname"],
            "camera": data["camera"],
            "timestamp": utc_now(),
            "last_batch_id": None,
        },
    )

    # Inform dashboard.
    try:
        await wds_client.device_updated(device)
    except Exception as exc:
        log_event(
            "warning",
            "WDS_UPDATE_FAILED",
            str(exc),
            device_id=data["device_id"],
        )

    log_event(
        "info",
        "DEVICE_REGISTERED",
        "Edge device registered",
        device_id=data["device_id"],
    )

    return device


async def process_health(
    data: Dict[str, Any],
):

    device = update_device_health(
        data["device_id"],
        data,
    )

    try:
        await dbs_client.save_health(
            data
        )
    except Exception as exc:

        log_event(
            "warning",
            "HEALTH_DB_FAILED",
            str(exc),
            device_id=data["device_id"],
        )

    try:
        await wds_client.device_updated(
            device
        )
    except Exception as exc:

        log_event(
            "warning",
            "HEALTH_WDS_FAILED",
            str(exc),
            device_id=data["device_id"],
        )

    log_event(
        "info",
        "HEALTH_RECEIVED",
        "Device health received",
        device_id=data["device_id"],
    )

    return device


async def process_batch(
    batch: Dict[str, Any],
):

    batch_id = batch["batch_id"]
    device_id = batch["device_id"]

    log_event(
        "info",
        "BATCH_RECEIVED",
        "Image batch received",
        device_id=device_id,
        batch_id=batch_id,
        metadata={
            "image_count": len(batch["images"])
        },
    )

    # Save initial batch state.
    db_batch = {
        **batch,
        "status": BatchStatus.RECEIVED.value,
        "received_at": utc_now().isoformat(),
    }

    try:

        await dbs_client.save_batch(
            db_batch
        )

    except Exception as exc:

        log_event(
            "error",
            "BATCH_DB_FAILED",
            str(exc),
            device_id=device_id,
            batch_id=batch_id,
        )

    # Mark as queued.
    try:

        await dbs_client.mark_queued(
            batch_id
        )

    except Exception:
        pass

    log_event(
        "info",
        "BATCH_QUEUED",
        "Batch queued for AI analysis",
        device_id=device_id,
        batch_id=batch_id,
    )

    # Start asynchronous analysis.
    asyncio.create_task(
        analyze_batch(batch)
    )

    return {
        "batch_id": batch_id,
        "status": BatchStatus.QUEUED.value,
    }


async def analyze_batch(
    batch: Dict[str, Any],
):

    batch_id = batch["batch_id"]
    device_id = batch["device_id"]

    try:

        await dbs_client.mark_processing(
            batch_id
        )

    except Exception:
        pass

    log_event(
        "info",
        "ANALYSIS_STARTED",
        "Sending batch to IAS",
        device_id=device_id,
        batch_id=batch_id,
    )

    try:

        result = await ias_client.analyze_batch(
            batch
        )

        result["status"] = (
            BatchStatus.COMPLETED.value
        )

        await dbs_client.save_result(
            result
        )

        log_event(
            "info",
            "ANALYSIS_COMPLETED",
            "AI analysis completed",
            device_id=device_id,
            batch_id=batch_id,
            metadata=result,
        )

        # Tell dashboard.
        try:

            await wds_client.batch_result(
                result
            )

        except Exception as exc:

            log_event(
                "warning",
                "WDS_RESULT_FAILED",
                str(exc),
                device_id=device_id,
                batch_id=batch_id,
            )

        # Enforce three-batch retention.
        try:

            await dbs_client.cleanup_batches(
                device_id
            )

        except Exception as exc:

            log_event(
                "warning",
                "RETENTION_FAILED",
                str(exc),
                device_id=device_id,
            )

    except Exception as exc:

        error_result = {
            "batch_id": batch_id,
            "device_id": device_id,
            "status": BatchStatus.FAILED.value,
            "error": str(exc),
        }

        try:

            await dbs_client.save_result(
                error_result
            )

        except Exception:
            pass

        log_event(
            "error",
            "ANALYSIS_FAILED",
            str(exc),
            device_id=device_id,
            batch_id=batch_id,
        )

        try:

            await wds_client.batch_result(
                error_result
            )

        except Exception:
            pass