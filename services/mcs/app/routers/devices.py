from fastapi import APIRouter, Depends, Header, HTTPException

from ..config import settings
from ..models import DeviceRegistrationRequest
from ..services import register_device
from ..state import get_device, get_devices
from ..auth import verify_edge_token


router = APIRouter(
    prefix="/api/v1/devices",
    tags=["devices"],
)


@router.post(
    "/register",
    dependencies=[Depends(verify_edge_token)],
)
async def register(
    request: DeviceRegistrationRequest,
):

    device = await register_device(
        request.model_dump(mode="json")
    )

    return {
        "success": True,
        "device": device,
    }


@router.get("/")
async def list_devices():

    return {
        "devices": get_devices()
    }


@router.get("/{device_id}")
async def get_device_info(
    device_id: str,
):

    device = get_device(device_id)

    if not device:

        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return device