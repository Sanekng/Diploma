from typing import Any, Dict

import httpx
from fastapi.encoders import jsonable_encoder

from .config import settings


class ServiceClient:

    def __init__(self):
        self.timeout = settings.request_timeout_seconds

    async def post(
        self,
        url: str,
        payload: Dict[str, Any],
    ):

        encoded_payload = jsonable_encoder(
            payload
        )

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.post(
                url,
                json=encoded_payload,
            )

            response.raise_for_status()

            return response.json()

    async def patch(
        self,
        url: str,
        payload: Dict[str, Any],
    ):

        encoded_payload = jsonable_encoder(
            payload
        )

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.patch(
                url,
                json=encoded_payload,
            )

            response.raise_for_status()

            return response.json()


class DBSClient(ServiceClient):

    async def register_device(
        self,
        device: Dict[str, Any],
    ):

        location = device.get(
            "location"
        ) or {}

        payload = {
            "device_id": device["device_id"],
            "hostname": device["hostname"],
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "camera_model": (
                device.get("camera") or {}
            ).get("model"),
            "registered_at": device["registered_at"],
            "metadata": {
                "device_type": device.get(
                    "device_type"
                ),
            },
        }

        return await self.post(
            f"{settings.dbs_url}/api/v1/devices/register",
            payload,
        )

    async def save_health(
        self,
        health: Dict[str, Any],
    ):

        payload = {
            "status": health.get(
                "status",
                "ONLINE",
            ),
            "timestamp": health[
                "timestamp"
            ],
            "metadata": {
                "hostname": health.get(
                    "hostname"
                ),
                "camera": health.get(
                    "camera"
                ),
                "last_batch_id": health.get(
                    "last_batch_id"
                ),
            },
        }

        return await self.post(
            (
                f"{settings.dbs_url}/api/v1/devices/"
                f"{health['device_id']}/health"
            ),
            payload,
        )

    async def save_batch(
        self,
        batch: Dict[str, Any],
    ):

        return await self.post(
            f"{settings.dbs_url}/api/v1/batches",
            batch,
        )

    async def save_result(
        self,
        result: Dict[str, Any],
    ):

        return await self.patch(
            (
                f"{settings.dbs_url}/api/v1/batches/"
                f"{result['batch_id']}/result"
            ),
            result,
        )

    async def mark_queued(
        self,
        batch_id: str,
    ):

        return await self.post(
            (
                f"{settings.dbs_url}/api/v1/batches/"
                f"{batch_id}/queued"
            ),
            {},
        )

    async def mark_processing(
        self,
        batch_id: str,
    ):

        return await self.post(
            (
                f"{settings.dbs_url}/api/v1/batches/"
                f"{batch_id}/processing"
            ),
            {},
        )

    async def save_log(
        self,
        log: Dict[str, Any],
    ):

        return await self.post(
            f"{settings.dbs_url}/api/v1/logs",
            log,
        )

    async def cleanup_batches(
        self,
        device_id: str,
    ):

        return await self.post(
            f"{settings.dbs_url}/api/v1/batches/cleanup",
            {
                "device_id": device_id,
                "keep": settings.batches_to_keep_per_device,
            },
        )


class IASClient(ServiceClient):

    async def analyze_batch(
        self,
        batch: Dict[str, Any],
    ):

        return await self.post(
            f"{settings.ias_url}/api/v1/analyze",
            batch,
        )


class WDSClient(ServiceClient):

    async def device_updated(
        self,
        device: Dict[str, Any],
    ):

        return await self.post(
            f"{settings.wds_url}/api/v1/events/device",
            device,
        )

    async def batch_result(
        self,
        result: Dict[str, Any],
    ):

        return await self.post(
            f"{settings.wds_url}/api/v1/events/batch",
            result,
        )


dbs_client = DBSClient()
ias_client = IASClient()
wds_client = WDSClient()