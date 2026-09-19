from fastapi import APIRouter, HTTPException, Query

from ..models import (
    RegisterDeviceRequest,
    UpdateDeviceHealthRequest,
)
from ..repositories import (
    get_device,
    get_devices,
    register_device,
    update_device_health,
)


router = APIRouter(
    prefix="/api/v1/devices",
    tags=["devices"],
)


@router.post(
    "/register"
)
def register(
    request: RegisterDeviceRequest,
):

    return register_device(
        request.model_dump()
    )


@router.get("")
def list_devices(
    skip: int = Query(
        default=0,
        ge=0,
    ),

    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):

    return {
        "devices": get_devices(
            skip=skip,
            limit=limit,
        )
    }


@router.get(
    "/{device_id}"
)
def device(
    device_id: str,
):

    result = get_device(
        device_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    return result


@router.post(
    "/{device_id}/health"
)
def update_health(
    device_id: str,
    request: UpdateDeviceHealthRequest,
):

    existing = get_device(
        device_id
    )

    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    return update_device_health(
        device_id,
        request.model_dump(),
    )