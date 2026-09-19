from fastapi import APIRouter, Query

from ..models import CreateLogRequest
from ..repositories import (
    create_log,
    get_logs,
)


router = APIRouter(
    prefix="/api/v1/logs",
    tags=["logs"],
)


@router.post("")
def create(
    request: CreateLogRequest,
):

    return create_log(
        request.model_dump()
    )


@router.get("")
def list_logs(
    device_id: str | None = Query(
        default=None
    ),

    batch_id: str | None = Query(
        default=None
    ),

    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):

    return {
        "logs": get_logs(
            device_id=device_id,
            batch_id=batch_id,
            limit=limit,
        )
    }