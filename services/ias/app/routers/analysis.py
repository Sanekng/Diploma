import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..model_manager import model_manager
from ..models import (
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
)
from ..predictor import analyze_images


logger = logging.getLogger("ias.analysis")


router = APIRouter(
    prefix="/api/v1",
    tags=["analysis"],
)


@router.post(
    "/analyze",
    response_model=AnalyzeBatchResponse,
)
async def analyze_batch(
    request: AnalyzeBatchRequest,
):

    # --------------------------------------------------------
    # Validate model
    # --------------------------------------------------------

    if not model_manager.is_loaded:

        raise HTTPException(
            status_code=503,
            detail=(
                "AI model is not loaded. "
                "Train the model before using IAS."
            ),
        )

    # --------------------------------------------------------
    # Validate batch
    # --------------------------------------------------------

    if (
        len(request.images)
        != settings.expected_images_per_batch
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                f"Expected "
                f"{settings.expected_images_per_batch} "
                f"images, received "
                f"{len(request.images)}."
            ),
        )

    # --------------------------------------------------------
    # Validate sequence numbers
    # --------------------------------------------------------

    sequence_numbers = sorted(
        image.sequence_number
        for image in request.images
    )

    expected_sequences = list(
        range(
            1,
            settings.expected_images_per_batch + 1,
        )
    )

    if sequence_numbers != expected_sequences:

        raise HTTPException(
            status_code=400,
            detail=(
                "Image sequence numbers are invalid. "
                f"Expected {expected_sequences}, "
                f"received {sequence_numbers}."
            ),
        )

    # --------------------------------------------------------
    # Sort images
    # --------------------------------------------------------

    images = sorted(
        request.images,
        key=lambda image: image.sequence_number,
    )

    logger.info(
        "Starting analysis: batch=%s device=%s",
        request.batch_id,
        request.device_id,
    )

    # --------------------------------------------------------
    # AI inference
    # --------------------------------------------------------

    try:

        (
            batch_prediction,
            confidence,
            image_predictions,
        ) = analyze_images(
            images
        )

    except FileNotFoundError as exc:

        logger.error(
            "Image not found: %s",
            exc,
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:

        logger.exception(
            "AI analysis failed."
        )

        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {exc}",
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = AnalyzeBatchResponse(
        batch_id=request.batch_id,
        device_id=request.device_id,

        prediction=batch_prediction,

        confidence=confidence,

        model_id=settings.model_id,
        model_version=settings.model_version,

        image_predictions=image_predictions,

        analyzed_at=datetime.now(
            timezone.utc
        ),
    )

    logger.info(
        "Analysis completed: batch=%s prediction=%s confidence=%.4f",
        request.batch_id,
        batch_prediction.value,
        confidence,
    )

    return result