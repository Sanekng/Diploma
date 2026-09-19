import json
import logging
import os
from pathlib import Path

import tensorflow as tf
from sklearn.metrics import classification_report
from tensorflow import keras
from tensorflow.keras import layers

# ============================================================
# GPU Setup - Fix 1: Install tensorflow-directml
# ============================================================

def setup_gpu():
    """Configure DirectML for Windows GPU acceleration."""
    
    # Try DirectML first (Windows)
    dml_devices = tf.config.list_physical_devices('DML')
    if dml_devices:
        print(f"✅ Found {len(dml_devices)} DirectML device(s)")
        for i, device in enumerate(dml_devices):
            print(f"  - Device {i}: {device}")
        return True
    
    # Try standard GPU (WSL2/Linux)
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f"✅ Found {len(gpus)} GPU(s)")
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        return True
    
    print("❌ No GPU/DirectML found, using CPU")
    return False

# Run setup
gpu_available = setup_gpu()
if not gpu_available:
    print("⚠️  Training will be slower on CPU")

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "fire_detection_model.keras"
METRICS_PATH = MODEL_DIR / "training_metrics.json"

# Fix 2: Use 384x384 instead of 512x512 for better compatibility
IMAGE_SIZE = (384, 384)  # Better balance for MobileNetV2
BATCH_SIZE = 32 if gpu_available else 16
SEED = 42
VALIDATION_SPLIT = 0.2
EPOCHS = 10
FINE_TUNE_EPOCHS = 3  # Reduced from 5 to prevent overfitting

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ias.training")

# ============================================================
# Dataset Loading
# ============================================================

def load_datasets():
    """Load and prepare datasets."""
    logger.info("Loading dataset from %s with image size %s", DATA_DIR, IMAGE_SIZE)

    train_dataset = tf.keras.utils.image_dataset_from_directory(
        DATA_DIR,
        validation_split=VALIDATION_SPLIT,
        subset="training",
        seed=SEED,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="binary",
        class_names=["non-fire", "fire"],
        shuffle=True,
    )

    validation_dataset = tf.keras.utils.image_dataset_from_directory(
        DATA_DIR,
        validation_split=VALIDATION_SPLIT,
        subset="validation",
        seed=SEED,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="binary",
        class_names=["non-fire", "fire"],
        shuffle=False,
    )

    logger.info("Classes: %s", train_dataset.class_names)
    return train_dataset, validation_dataset

# ============================================================
# Model Creation - Fix 3: Better model for larger images
# ============================================================

def create_model():
    """Create the model architecture."""
    logger.info("Creating model with input size %s", IMAGE_SIZE)

    # Data augmentation
    data_augmentation = keras.Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.1),
        layers.RandomZoom(0.1),
        layers.RandomBrightness(0.1),
        layers.RandomContrast(0.1),
    ], name="data_augmentation")

    # Fix 3: Use EfficientNetV2S for better large image support
    base_model = tf.keras.applications.EfficientNetV2S(
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3),
        include_top=False,
        weights="imagenet",
    )
    
    # Freeze base model
    base_model.trainable = False

    inputs = keras.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3))
    x = data_augmentation(inputs)
    x = tf.keras.applications.efficientnet_v2.preprocess_input(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(128, activation='relu')(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)

    model = keras.Model(inputs, outputs)

    # Fix 4: Remove AUC metric (DirectML compatibility issue)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.0001),
        loss=keras.losses.BinaryCrossentropy(),
        metrics=[
            "accuracy",
            keras.metrics.Precision(name="precision"),
            keras.metrics.Recall(name="recall"),
        ],
    )

    model.summary(print_fn=logger.info)
    return model, base_model

# ============================================================
# Training Loop
# ============================================================

def train():
    """Main training function."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Starting training with:")
    logger.info("  - Image size: %s", IMAGE_SIZE)
    logger.info("  - Batch size: %d", BATCH_SIZE)
    logger.info("  - GPU available: %s", gpu_available)
    logger.info("=" * 60)

    # Load and prepare datasets
    train_dataset, validation_dataset = load_datasets()
    
    # Optimize datasets
    autotune = tf.data.AUTOTUNE
    train_dataset = train_dataset.cache().prefetch(autotune)
    validation_dataset = validation_dataset.cache().prefetch(autotune)

    # Create model
    model, base_model = create_model()

    # Callbacks
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=3,
            restore_best_weights=True,
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=MODEL_PATH,
            monitor="val_loss",
            save_best_only=True,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-7,
        ),
    ]

    # Stage 1: Transfer Learning
    logger.info("Starting transfer-learning stage...")
    history = model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=EPOCHS,
        callbacks=callbacks,
        verbose=1,
    )

    # Stage 2: Fine Tuning (with fewer epochs)
    logger.info("Starting fine-tuning stage...")
    base_model.trainable = True
    
    # Freeze early layers
    for layer in base_model.layers[:50]:  # Freeze fewer layers for fine-tuning
        layer.trainable = False

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-5),
        loss=keras.losses.BinaryCrossentropy(),
        metrics=[
            "accuracy",
            keras.metrics.Precision(name="precision"),
            keras.metrics.Recall(name="recall"),
        ],
    )

    fine_tune_history = model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=EPOCHS + FINE_TUNE_EPOCHS,
        initial_epoch=len(history.history["loss"]),
        callbacks=callbacks,
        verbose=1,
    )

    # Evaluation
    logger.info("Evaluating model...")
    evaluation = model.evaluate(validation_dataset, return_dict=True, verbose=1)
    logger.info("Evaluation: %s", evaluation)

    # ... (rest of the code remains the same)
    
    logger.info("=" * 60)
    logger.info("Training completed successfully!")
    logger.info("Final Accuracy: %.4f", evaluation["accuracy"])
    logger.info("Final Precision: %.4f", evaluation["precision"])
    logger.info("Final Recall: %.4f", evaluation["recall"])
    logger.info("=" * 60)

if __name__ == "__main__":
    train()