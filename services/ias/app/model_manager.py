import logging
from pathlib import Path
from typing import Optional
import numpy as np

import tensorflow as tf

from .config import settings


logger = logging.getLogger("ias.model")


class ModelManager:

    def __init__(self):
        self.model: Optional[tf.keras.Model] = None

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def load(self) -> None:

        model_path = Path(settings.model_path)

        if not model_path.exists():
            logger.error(
                "Model file does not exist: %s",
                model_path,
            )
            self.model = None
            return

        logger.info(
            "Loading model from %s",
            model_path,
        )

        try:
            model = tf.keras.models.load_model(
                model_path,
                compile=False,
            )

            logger.info(
                "Model name: %s",
                model.name,
            )

            logger.info(
                "Model input shape: %s",
                model.input_shape,
            )

            logger.info(
                "Model output shape: %s",
                model.output_shape,
            )

            expected_input_shape = (
                None,
                settings.image_height,
                settings.image_width,
                3,
            )

            if tuple(model.input_shape) != expected_input_shape:
                raise RuntimeError(
                    "Unexpected model input shape. "
                    f"Expected {expected_input_shape}, "
                    f"got {model.input_shape}"
                )

            expected_output_shape = (None, 1)

            if tuple(model.output_shape) != expected_output_shape:
                raise RuntimeError(
                    "Unexpected model output shape. "
                    f"Expected {expected_output_shape}, "
                    f"got {model.output_shape}"
                )

            dummy_input = np.zeros(
                (
                    1,
                    settings.image_height,
                    settings.image_width,
                    3,
                ),
                dtype=np.float32,
            )

            dummy_output = model.predict(
                dummy_input,
                verbose=0,
            )

            logger.info(
                "Test prediction shape: %s",
                dummy_output.shape,
            )

            logger.info(
                "Test prediction: %s",
                dummy_output,
            )

            probability = float(dummy_output[0][0])

            if not 0.0 <= probability <= 1.0:
                raise RuntimeError(
                    "Model output is not a valid sigmoid probability: "
                    f"{probability}"
                )

            self.model = model

            logger.info(
                "ResNet50 fire detection model loaded successfully."
            )

        except Exception:
            self.model = None

            logger.exception(
                "Failed to load/validate model from %s",
                model_path,
            )

            raise

    def reload(self) -> None:

        self.model = None

        self.load()

    def predict(
        self,
        image_tensor,
    ):

        if self.model is None:

            raise RuntimeError(
                "AI model is not loaded."
            )

        return self.model.predict(
            image_tensor,
            verbose=0,
        )


model_manager = ModelManager()