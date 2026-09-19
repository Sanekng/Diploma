import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATA_DIR = (
    PROJECT_ROOT / "data"
)

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "fire_detection_model.keras"
)

IMAGE_SIZE = (
    224,
    224,
)

BATCH_SIZE = 32

SEED = 42

VALIDATION_SPLIT = 0.2


def main():

    print(
        f"Loading model: {MODEL_PATH}"
    )

    model = tf.keras.models.load_model(
        MODEL_PATH
    )

    dataset = (
        tf.keras.utils.image_dataset_from_directory(
            DATA_DIR,

            validation_split=VALIDATION_SPLIT,

            subset="validation",

            seed=SEED,

            image_size=IMAGE_SIZE,

            batch_size=BATCH_SIZE,

            label_mode="binary",

            class_names=[
                "non-fire",
                "fire",
            ],

            shuffle=False,
        )
    )

    y_true = []

    y_pred = []

    probabilities = []

    for images, labels in dataset:

        prediction = model.predict(
            images,
            verbose=0,
        )

        probabilities.extend(
            prediction.flatten()
        )

        predictions = (
            prediction >= 0.5
        ).astype(int).flatten()

        y_pred.extend(
            predictions
        )

        y_true.extend(
            labels.numpy().astype(int)
        )

    print(
        "\nClassification report:"
    )

    print(
        classification_report(
            y_true,
            y_pred,
            target_names=[
                "NON_FIRE",
                "FIRE",
            ],
            zero_division=0,
        )
    )

    print(
        "\nConfusion matrix:"
    )

    print(
        confusion_matrix(
            y_true,
            y_pred,
        )
    )


if __name__ == "__main__":
    main()