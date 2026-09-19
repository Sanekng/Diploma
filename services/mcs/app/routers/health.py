from fastapi import APIRouter, Depends, Header, HTTPException

from ..config import settings
from ..models import DeviceHealthRequest
from ..services import process_health
from ..auth import verify_edge_token


router = APIRouter(
    prefix="/api/v1/devices",
    tags=["health"],
)

@router.post(
    "/health",
    dependencies=[Depends(verify_edge_token)],
)
async def health(
    request: DeviceHealthRequest,
):

    result = await process_health(
        request.model_dump(mode="json")
    )

    return {
        "success": True,
        "device": result,
    }