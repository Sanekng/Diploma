from datetime import datetime, timezone
from typing import Dict, Any


devices: Dict[str, Dict[str, Any]] = {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def update_device_health(
    device_id: str,
    health: Dict[str, Any],
) -> Dict[str, Any]:

    existing = devices.get(device_id, {})

    existing.update(
        {
            "device_id": device_id,
            "hostname": health.get("hostname"),
            "status": "ONLINE",
            "camera": health.get("camera"),
            "last_heartbeat": health.get("timestamp"),
            "last_batch_id": health.get("last_batch_id"),
            "updated_at": utc_now(),
        }
    )

    devices[device_id] = existing

    return existing


def get_device(device_id: str):
    return devices.get(device_id)


def get_devices():
    return list(devices.values())


def mark_stale_devices(
    offline_after_seconds: int,
):
    now = utc_now()
    stale_devices = []

    for device in devices.values():
        last_heartbeat = device.get("last_heartbeat")

        if isinstance(last_heartbeat, str):
            last_heartbeat = datetime.fromisoformat(
                last_heartbeat.replace("Z", "+00:00")
            )

        if not isinstance(last_heartbeat, datetime):
            continue

        if last_heartbeat.tzinfo is None:
            last_heartbeat = last_heartbeat.replace(
                tzinfo=timezone.utc
            )

        if (
            device.get("status") == "ONLINE"
            and (now - last_heartbeat).total_seconds()
            >= offline_after_seconds
        ):
            device["status"] = "OFFLINE"
            device["updated_at"] = now
            stale_devices.append(device)

    return stale_devices