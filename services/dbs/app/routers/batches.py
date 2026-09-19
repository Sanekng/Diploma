from fastapi import APIRouter, HTTPException, Query

from ..models import (
    BatchStatus,
    CleanupBatchesRequest,
    CreateBatchRequest,
    UpdateBatchResultRequest,
)
from ..repositories import (
    create_batch,
    delete_old_batches_for_device,
    get_batch,
    get_device_batches,
    get_latest_batches,
    get_device,
    update_batch_result,
)


router = APIRouter(
    prefix="/api/v1/batches",
    tags=["batches"],
)


@router.post("")
def create(
    request: CreateBatchRequest,
):

    device = get_device(
        request.device_id
    )

    if device is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Device is not registered."
            ),
        )

    existing = get_batch(
        request.batch_id
    )

    if existing:

        return existing

    try:

        result = create_batch(
            request.model_dump()
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return result


@router.get("")
def latest_batches(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
):

    return {
        "batches": get_latest_batches(
            limit
        )
    }


@router.get(
    "/{batch_id}"
)
def batch(
    batch_id: str,
):

    result = get_batch(
        batch_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return result


@router.get(
    "/device/{device_id}"
)
def device_batches(
    device_id: str,

    limit: int = Query(
        default=3,
        ge=1,
        le=100,
    ),
):

    device = get_device(
        device_id
    )

    if device is None:

        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    return {
        "device_id": device_id,

        "batches": get_device_batches(
            device_id,
            limit,
        )
    }


@router.patch(
    "/{batch_id}/result"
)
def result(
    batch_id: str,
    request: UpdateBatchResultRequest,
):

    existing = get_batch(
        batch_id
    )

    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return update_batch_result(
        batch_id,
        request.model_dump()
    )


@router.post(
    "/{batch_id}/queued"
)
def mark_queued(
    batch_id: str,
):

    existing = get_batch(
        batch_id
    )

    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return update_batch_result(
        batch_id,
        {
            "status":
                BatchStatus.QUEUED.value
        },
    )


@router.post(
    "/{batch_id}/processing"
)
def mark_processing(
    batch_id: str,
):

    existing = get_batch(
        batch_id
    )

    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return update_batch_result(
        batch_id,
        {
            "status":
                BatchStatus.PROCESSING.value
        },
    )


@router.post(
    "/{batch_id}/failed"
)
def mark_failed(
    batch_id: str,
    error: str,
):

    existing = get_batch(
        batch_id
    )

    if existing is None:

        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return update_batch_result(
        batch_id,
        {
            "status":
                BatchStatus.FAILED.value,

            "error": error,
        },
    )


@router.post(
    "/cleanup"
)
def cleanup(
    request: CleanupBatchesRequest,
):

    device = get_device(
        request.device_id
    )

    if device is None:

        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    deleted = delete_old_batches_for_device(
        request.device_id,
        request.keep,
    )

    return {
        "device_id": request.device_id,
        "deleted": deleted,
        "kept": request.keep,
    }