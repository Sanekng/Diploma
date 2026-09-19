import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import numpy as np
import tensorflow as tf
from PIL import Image

from .config import settings
from .model_manager import model_manager
from .models import (
    ImageInput,
    ImagePrediction,
    Prediction,
)


logger = logging.getLogger("ias.predictor")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_image_path(
    storage_path: str,
) -> Path:

    storage_root = Path(
        settings.storage_path
    ).resolve()

    requested_path = (
        storage_root / storage_path
    ).resolve()

    # Security check:
    # Don't allow a path such as ../../etc/passwd.
    if not requested_path.is_relative_to(
        storage_root
    ):
        raise ValueError(
            "Image path is outside the configured "
            "storage directory."
        )

    return requested_path


def load_image(
    image_path: Path,
) -> np.ndarray:

    if not image_path.exists():

        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = Image.open(
        image_path
    )

    image = image.convert("RGB")

    image = image.resize(
        (
            settings.image_width,
            settings.image_height,
        )
    )

    image_array = np.asarray(
        image,
        dtype=np.float32,
    )

    return image_array


def preprocess_image(
    image_path: Path,
) -> np.ndarray:

    image_array = load_image(
        image_path
    )

    image_array = image_array.astype(np.float32)

    return image_array


def predict_single_image(
    image: ImageInput,
) -> ImagePrediction:

    image_path = resolve_image_path(
        image.storage_path
    )

    image_tensor = preprocess_image(
        image_path
    )

    image_tensor = np.expand_dims(
        image_tensor,
        axis=0,
    )

    prediction = model_manager.predict(
        image_tensor
    )

    logger.info(
        "Model output for %s: shape=%s values=%s",
        image.filename,
        prediction.shape,
        prediction,
    )

    fire_probability = float(
        prediction[0][0]
    )

    fire_probability = float(
        np.clip(
            fire_probability,
            0.0,
            1.0,
        )
    )

    if fire_probability >= settings.fire_threshold:
        result = Prediction.FIRE
    else:
        result = Prediction.NON_FIRE

    return ImagePrediction(
        image_id=image.image_id,
        sequence_number=image.sequence_number,
        filename=image.filename,
        fire_probability=fire_probability,
        prediction=result,
    )

def calculate_batch_result(
    predictions: List[ImagePrediction],
) -> Tuple[Prediction, float]:

    if not predictions:

        raise ValueError(
            "Cannot calculate result for empty batch."
        )

    probabilities = [
        prediction.fire_probability
        for prediction in predictions
    ]

    average_probability = float(
        np.mean(probabilities)
    )

    if average_probability >= settings.fire_threshold:

        batch_prediction = Prediction.FIRE

    else:

        batch_prediction = Prediction.NON_FIRE

    return (
        batch_prediction,
        average_probability,
    )


def analyze_images(
    images: List[ImageInput],
):

    predictions = []

    for image in images:

        logger.info(
            "Analyzing image %s",
            image.filename,
        )

        prediction = predict_single_image(
            image
        )

        predictions.append(
            prediction
        )

    batch_prediction, confidence = (
        calculate_batch_result(
            predictions
        )
    )

    return (
        batch_prediction,
        confidence,
        predictions,
    )