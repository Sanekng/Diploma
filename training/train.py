#!/usr/bin/env python3
"""
Fire Detection Training Script for Thesis
==========================================
Compares MobileNetV2, EfficientNet-B0, and ResNet50
with comprehensive visualizations for thesis presentation.
"""

import json
import logging
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    roc_curve, 
    auc,
    precision_recall_curve,
    f1_score
)
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, applications
from sklearn.utils.class_weight import compute_class_weight

# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "prepared_data"
MODEL_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42
EPOCHS = 20
FINE_TUNE_EPOCHS = 8  # Увеличил для лучшего обучения

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fire_detection.training")

# ============================================================
# GPU Setup with fallback
# ============================================================

def setup_gpu():
    """Configure GPU if available, otherwise use CPU."""
    try:
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            logger.info(f"GPU devices found: {len(gpus)}")
            return True
    except Exception as e:
        logger.warning(f"GPU setup failed: {e}")
    
    logger.warning("No GPU found – training on CPU (will be slower)")
    return False

gpu_available = setup_gpu()

# ============================================================
# Dataset Loading with Augmentation
# ============================================================

def load_datasets():
    """Load and prepare datasets with augmentation."""
    logger.info("Loading datasets from %s", DATA_DIR)

    def make_ds(subdir, shuffle=False):
        ds = tf.keras.utils.image_dataset_from_directory(
            DATA_DIR / subdir,
            labels="inferred",
            label_mode="binary",
            class_names=["non-fire", "fire"],
            image_size=IMAGE_SIZE,
            batch_size=BATCH_SIZE,
            shuffle=shuffle,
            seed=SEED,
        )
        return ds

    train_ds = make_ds("train", shuffle=True)
    val_ds = make_ds("val", shuffle=False)
    test_ds = make_ds("test", shuffle=False)

    # Class distribution check
    def count_classes(dataset, name):
        fire = non_fire = 0
        for _, labels in dataset:
            fire += int(tf.reduce_sum(labels))
            non_fire += int(tf.reduce_sum(1 - labels))
        logger.info(f"{name:8} → non-fire: {non_fire:4d} | fire: {fire:4d}")
        return non_fire, fire

    logger.info("Class distribution:")
    n_non_fire, n_fire = count_classes(train_ds, "Train")
    count_classes(val_ds, "Val")
    count_classes(test_ds, "Test")

    # Class weights
    class_weights = compute_class_weight(
        class_weight="balanced",
        classes=np.array([0, 1]),
        y=np.concatenate([[0] * n_non_fire, [1] * n_fire])
    )
    class_weight_dict = {0: class_weights[0], 1: class_weights[1]}
    logger.info(f"Class weights: {class_weight_dict}")

    # Data augmentation
    data_augmentation = keras.Sequential([
        layers.RandomFlip("horizontal"),
        layers.RandomRotation(0.15),
        layers.RandomZoom(0.15),
        layers.RandomContrast(0.15),
        layers.RandomBrightness(0.12),
        layers.RandomTranslation(0.1, 0.1),
    ], name="data_augmentation")

    def prepare(ds, training=False):
        if training:
            ds = ds.map(
                lambda x, y: (data_augmentation(x, training=True), y),
                num_parallel_calls=tf.data.AUTOTUNE,
            )
        return ds.cache().prefetch(tf.data.AUTOTUNE)

    train_ds = prepare(train_ds, training=True)
    val_ds = prepare(val_ds, training=False)
    test_ds = prepare(test_ds, training=False)

    return train_ds, val_ds, test_ds, class_weight_dict

# ============================================================
# Model Builders (Your requested architectures)
# ============================================================

def build_mobilenetv2():
    """MobileNetV2 - lightest model for weak hardware."""
    base = applications.MobileNetV2(
        input_shape=(*IMAGE_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False

    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = applications.mobilenet_v2.preprocess_input(inputs)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)
    return keras.Model(inputs, outputs, name="MobileNetV2")

def build_efficientnetb0():
    """EfficientNet-B0 - balanced performance/efficiency."""
    base = applications.EfficientNetV2B0(
        input_shape=(*IMAGE_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False

    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = applications.efficientnet_v2.preprocess_input(inputs)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.35)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)
    return keras.Model(inputs, outputs, name="EfficientNetV2B0")

def build_resnet50():
    """ResNet50 - heavier baseline for comparison."""
    base = applications.ResNet50(
        input_shape=(*IMAGE_SIZE, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False

    inputs = keras.Input(shape=(*IMAGE_SIZE, 3))
    x = applications.resnet50.preprocess_input(inputs)
    x = base(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.4)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)
    return keras.Model(inputs, outputs, name="ResNet50")

# ============================================================
# Training & Evaluation
# ============================================================

def compile_model(model, lr=1e-4):
    """Compile model with appropriate metrics."""
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=lr),
        loss="binary_crossentropy",
        metrics=[
            "accuracy",
            keras.metrics.Precision(name="precision"),
            keras.metrics.Recall(name="recall"),
            keras.metrics.AUC(name="auc"),
        ],
    )
    return model

def evaluate_model(model, dataset):
    """Comprehensive evaluation with all metrics."""
    y_true, y_prob = [], []
    
    for images, labels in dataset:
        preds = model.predict(images, verbose=0)
        y_true.extend(labels.numpy().flatten())
        y_prob.extend(preds.flatten())

    y_true = np.array(y_true)
    y_prob = np.array(y_prob)
    y_pred = (y_prob > 0.5).astype(int)

    # All metrics
    report = classification_report(
        y_true, y_pred,
        target_names=["non-fire", "fire"],
        output_dict=True,
        zero_division=0,
    )
    
    cm = confusion_matrix(y_true, y_pred)
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    roc_auc = auc(fpr, tpr)
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    
    return {
        "report": report,
        "confusion_matrix": cm.tolist(),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "accuracy": float(report["accuracy"]),
        "precision_fire": float(report["fire"]["precision"]),
        "recall_fire": float(report["fire"]["recall"]),
        "f1_fire": float(report["fire"]["f1-score"]),
        "precision_non_fire": float(report["non-fire"]["precision"]),
        "recall_non_fire": float(report["non-fire"]["recall"]),
        "f1_non_fire": float(report["non-fire"]["f1-score"]),
        "roc_auc": float(roc_auc),
        "y_true": y_true.tolist(),
        "y_prob": y_prob.tolist(),
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "precision_curve": precision.tolist(),
        "recall_curve": recall.tolist(),
    }

def train_one_model(model, train_ds, val_ds, test_ds, class_weight, name):
    """Train a single model with two-stage transfer learning."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Training: {name}")
    logger.info(f"{'='*60}")

    model = compile_model(model, lr=1e-3)  # Higher LR for initial training

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=5,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-7,
            verbose=1,
        ),
    ]

    # Stage 1: Train only the top layers
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=EPOCHS,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=1,
    )

    # Stage 2: Fine-tune the entire model
    if name != "CustomCNN":
        # Unfreeze the base model
        for layer in model.layers:
            if hasattr(layer, "layers"):
                layer.trainable = True
                # Freeze early layers to prevent catastrophic forgetting
                for i, l in enumerate(layer.layers):
                    if i < len(layer.layers) * 0.6:  # Freeze first 60%
                        l.trainable = False
        
        # Recompile with lower learning rate
        model = compile_model(model, lr=1e-5)
        
        fine_tune_history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=FINE_TUNE_EPOCHS,
            class_weight=class_weight,
            callbacks=callbacks,
            verbose=1,
        )
        
        # Combine histories
        history.history['val_accuracy'].extend(fine_tune_history.history['val_accuracy'])
        history.history['accuracy'].extend(fine_tune_history.history['accuracy'])
        history.history['val_loss'].extend(fine_tune_history.history['val_loss'])
        history.history['loss'].extend(fine_tune_history.history['loss'])

    # Final evaluation
    results = evaluate_model(model, test_ds)
    results['history'] = history.history
    
    logger.info(
        f"{name:20} → Acc: {results['accuracy']:.4f} | "
        f"F1: {results['f1']:.4f} | "
        f"Recall(fire): {results['recall_fire']:.4f} | "
        f"AUC: {results['roc_auc']:.4f}"
    )
    
    return model, results

# ============================================================
# Visualization Functions
# ============================================================

def plot_confusion_matrix(cm, model_name, save_path):
    """Plot confusion matrix for thesis."""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['Non-Fire', 'Fire'],
                yticklabels=['Non-Fire', 'Fire'])
    plt.title(f'Confusion Matrix - {model_name}')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Confusion matrix saved: {save_path}")

def plot_training_history(history, model_name, save_path):
    """Plot training curves for thesis."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Accuracy
    ax1.plot(history['accuracy'], label='Train')
    ax1.plot(history['val_accuracy'], label='Validation')
    ax1.set_title(f'Accuracy - {model_name}')
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Accuracy')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Loss
    ax2.plot(history['loss'], label='Train')
    ax2.plot(history['val_loss'], label='Validation')
    ax2.set_title(f'Loss - {model_name}')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Loss')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Training history saved: {save_path}")

def plot_roc_curve(all_results, save_path):
    """Plot ROC curves for all models for comparison."""
    plt.figure(figsize=(10, 8))
    
    for model_name, results in all_results.items():
        fpr = np.array(results['fpr'])
        tpr = np.array(results['tpr'])
        roc_auc = results['roc_auc']
        plt.plot(fpr, tpr, label=f'{model_name} (AUC = {roc_auc:.3f})')
    
    plt.plot([0, 1], [0, 1], 'k--', label='Random')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curves Comparison')
    plt.legend(loc="lower right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"ROC curves saved: {save_path}")

def plot_precision_recall_curves(all_results, save_path):
    """Plot Precision-Recall curves for all models."""
    plt.figure(figsize=(10, 8))
    
    for model_name, results in all_results.items():
        precision = np.array(results['precision_curve'])
        recall = np.array(results['recall_curve'])
        f1_score_model = results['f1']
        plt.plot(recall, precision, label=f'{model_name} (F1 = {f1_score_model:.3f})')
    
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curves Comparison')
    plt.legend(loc="lower left")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Precision-Recall curves saved: {save_path}")

def plot_performance_comparison(all_results, save_path):
    """Bar chart comparing key metrics across models."""
    models = list(all_results.keys())
    metrics = ['accuracy', 'f1', 'recall_fire', 'precision_fire', 'roc_auc']
    metric_labels = ['Accuracy', 'F1-Score', 'Recall (Fire)', 'Precision (Fire)', 'ROC-AUC']
    
    x = np.arange(len(models))
    width = 0.15
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    for i, (metric, label) in enumerate(zip(metrics, metric_labels)):
        values = [all_results[m][metric] for m in models]
        offset = (i - len(metrics)/2) * width + width/2
        ax.bar(x + offset, values, width, label=label)
    
    ax.set_xlabel('Models')
    ax.set_ylabel('Score')
    ax.set_title('Model Performance Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=5)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 1.0)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Performance comparison saved: {save_path}")

def plot_model_complexity_comparison(model_sizes, save_path):
    """Show model size/complexity comparison."""
    plt.figure(figsize=(10, 6))
    
    names = list(model_sizes.keys())
    params = [model_sizes[n]['parameters'] / 1e6 for n in names]
    size_mb = [model_sizes[n]['size_mb'] for n in names]
    
    x = np.arange(len(names))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, params, width, label='Parameters (Millions)', color='skyblue')
    bars2 = ax.bar(x + width/2, size_mb, width, label='Model Size (MB)', color='lightcoral')
    
    ax.set_xlabel('Models')
    ax.set_ylabel('Value')
    ax.set_title('Model Complexity Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom')
    
    for bar in bars2:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Complexity comparison saved: {save_path}")

# ============================================================
# Main
# ============================================================

def main():
    """Main training and evaluation pipeline."""
    logger.info("Starting multi-model training for thesis...")
    
    # Load data
    train_ds, val_ds, test_ds, class_weight = load_datasets()

    # Model builders
    model_builders = {
        "MobileNetV2": build_mobilenetv2,
        "EfficientNetV2B0": build_efficientnetb0,
        "ResNet50": build_resnet50,
    }

    all_results = {}
    model_sizes = {}
    best_f1 = -1.0
    best_model = None
    best_name = None

    # Train each model
    for name, builder in model_builders.items():
        logger.info(f"\n{'='*70}")
        logger.info(f"Training {name}")
        logger.info(f"{'='*70}")
        
        # Clear session to save memory
        keras.backend.clear_session()
        
        model = builder()
        trained_model, results = train_one_model(
            model, train_ds, val_ds, test_ds, class_weight, name
        )

        all_results[name] = results
        
        # Save model
        model_path = MODEL_DIR / f"{name.lower()}.keras"
        trained_model.save(model_path)
        logger.info(f"Saved → {model_path}")

        # Get model size
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        params = trained_model.count_params()
        model_sizes[name] = {
            'parameters': params,
            'size_mb': size_mb
        }

        # Track best model
        if results["f1"] > best_f1:
            best_f1 = results["f1"]
            best_model = trained_model
            best_name = name

    # Save best model
    if best_model is not None:
        best_path = MODEL_DIR / "best_fire_model.keras"
        best_model.save(best_path)
        logger.info(f"\n{'='*70}")
        logger.info(f"BEST MODEL: {best_name} (F1 = {best_f1:.4f})")
        logger.info(f"Saved as → {best_path}")
        logger.info(f"{'='*70}")

    # Generate visualizations
    logger.info("\nGenerating visualizations for thesis...")
    
    # Confusion matrices
    for name, results in all_results.items():
        cm = np.array(results['confusion_matrix'])
        plot_confusion_matrix(cm, name, RESULTS_DIR / f"cm_{name.lower()}.png")
    
    # Training histories
    for name, results in all_results.items():
        plot_training_history(
            results['history'], 
            name, 
            RESULTS_DIR / f"history_{name.lower()}.png"
        )
    
    # ROC curves
    plot_roc_curve(all_results, RESULTS_DIR / "roc_curves.png")
    
    # Precision-Recall curves
    plot_precision_recall_curves(all_results, RESULTS_DIR / "pr_curves.png")
    
    # Performance comparison
    plot_performance_comparison(all_results, RESULTS_DIR / "performance_comparison.png")
    
    # Model complexity
    plot_model_complexity_comparison(model_sizes, RESULTS_DIR / "complexity_comparison.png")

    # Save complete results
    complete_results = {
        "timestamp": datetime.now().isoformat(),
        "image_size": list(IMAGE_SIZE),
        "batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "fine_tune_epochs": FINE_TUNE_EPOCHS,
        "gpu_available": gpu_available,
        "best_model": best_name,
        "best_f1": best_f1,
        "model_sizes": model_sizes,
        "models": all_results,
    }

    results_path = RESULTS_DIR / "complete_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(complete_results, f, indent=2)

    logger.info(f"\n{'='*70}")
    logger.info("TRAINING COMPLETED SUCCESSFULLY!")
    logger.info(f"Results saved to: {RESULTS_DIR}")
    logger.info(f"Best model: {best_name} (F1 = {best_f1:.4f})")
    logger.info(f"{'='*70}")

if __name__ == "__main__":
    main()