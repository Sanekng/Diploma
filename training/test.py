#!/usr/bin/env python3
"""
Fire Detection Inference with Model Comparison
===============================================
Tests all trained models on a single image and visualizes results.
For thesis: shows how different models perform on real-world images.
"""

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
import tensorflow as tf
from tensorflow import keras
import joblib
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================
IMAGE_SIZE = (224, 224)
CLASS_NAMES = ["non-fire", "fire"]
CONFIDENCE_THRESHOLD = 0.5  # Standard threshold

# Model paths (updated to use new models)
MODEL_PATHS = {
    "MobileNetV2": "models/mobilenetv2.keras",
    "EfficientNetV2B0": "models/efficientnetv2b0.keras",
    "ResNet50": "models/resnet50.keras",
    "Best Model": "models/best_fire_model.keras",  # This will be the best performer
}

# ============================================================
# Feature extraction for classical model (if needed)
# ============================================================
def extract_hsv_features(image_rgb):
    """
    Extract HSV features for classical ML models.
    Used for RandomForest baseline comparison.
    """
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    h_mean, s_mean, v_mean = np.mean(hsv, axis=(0, 1))
    h_std, s_std, v_std = np.std(hsv, axis=(0, 1))
    
    # Fire-like pixel ratio (orange-red + high saturation & value)
    mask = ((hsv[:,:,0] < 30) | (hsv[:,:,0] > 150)) & \
           (hsv[:,:,1] > 50) & (hsv[:,:,2] > 100)
    fire_ratio = np.sum(mask) / (image_rgb.shape[0] * image_rgb.shape[1])
    
    return np.array([[h_mean, s_mean, v_mean, h_std, s_std, v_std, fire_ratio]])

# ============================================================
# Load all models
# ============================================================
def load_models():
    """Load all trained models."""
    models = {}
    
    # Load deep learning models
    for name, path in MODEL_PATHS.items():
        try:
            if os.path.exists(path):
                models[name] = keras.models.load_model(path)
                logger.info(f"Loaded {name} from {path}")
            else:
                logger.warning(f"Model {name} not found at {path}")
        except Exception as e:
            logger.error(f"Failed to load {name}: {e}")
    
    # Try to load classical model if exists
    try:
        if os.path.exists("models/classical_randomforest.joblib"):
            models["RandomForest"] = joblib.load("models/classical_randomforest.joblib")
            logger.info("Loaded RandomForest model")
    except Exception as e:
        logger.warning(f"Could not load RandomForest: {e}")
    
    return models

# ============================================================
# Predict on single image
# ============================================================
def predict_image(models, image_path, show_visualization=True):
    """
    Run inference on a single image using all models.
    Returns predictions and visualizes results.
    """
    # Load image
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_rgb_display = cv2.resize(img_rgb, (640, 480))  # For display
    
    # Prepare image for deep learning models
    img_dl = cv2.resize(img_rgb, IMAGE_SIZE)
    img_dl = img_dl.astype("float32")
    img_dl = np.expand_dims(img_dl, axis=0)
    
    # Prepare features for classical model
    features = extract_hsv_features(img_rgb)
    
    # Store predictions
    predictions = {}
    
    # Run inference on each model
    for name, model in models.items():
        try:
            if name == "RandomForest":
                # Classical model
                prob = model.predict_proba(features)[0][1]
            else:
                # Deep learning model
                prob = float(model.predict(img_dl, verbose=0)[0][0])
            
            pred_class = "fire" if prob >= CONFIDENCE_THRESHOLD else "non-fire"
            confidence = prob if pred_class == "fire" else 1 - prob
            
            predictions[name] = {
                "probability": prob,
                "class": pred_class,
                "confidence": confidence,
                "correct": None  # Will be set if we know ground truth
            }
            
            logger.info(f"{name:20} → {pred_class:10} (prob: {prob:.4f})")
            
        except Exception as e:
            logger.error(f"Error predicting with {name}: {e}")
            predictions[name] = {"error": str(e)}
    
    # Visualize results
    if show_visualization:
        visualize_predictions(img_rgb_display, predictions, image_path)
    
    return predictions

# ============================================================
# Visualization for Thesis
# ============================================================
def visualize_predictions(image, predictions, image_path):
    """
    Create a comprehensive visualization for thesis.
    Shows: original image, prediction bars, confidence scores.
    """
    # Create figure with GridSpec for better layout
    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(2, 3, figure=fig, height_ratios=[2, 1], hspace=0.3, wspace=0.3)
    
    # ----- Left: Original Image -----
    ax_img = fig.add_subplot(gs[0, 0:2])
    ax_img.imshow(image)
    ax_img.set_title("Input Image", fontsize=14, fontweight='bold')
    ax_img.axis('off')
    
    # Add filename info
    filename = Path(image_path).name
    ax_img.text(10, 20, f"File: {filename}", color='white', 
                fontsize=10, bbox=dict(boxstyle="round", facecolor='black', alpha=0.7))
    
    # ----- Right: Model Results -----
    ax_results = fig.add_subplot(gs[0, 2])
    ax_results.axis('off')
    ax_results.set_title("Model Predictions", fontsize=14, fontweight='bold')
    
    # Plot each model's prediction
    y_pos = 0
    for i, (name, pred) in enumerate(predictions.items()):
        if "error" in pred:
            continue
            
        prob = pred["probability"]
        pred_class = pred["class"]
        confidence = pred["confidence"]
        
        # Color based on prediction
        color = '#FF6B6B' if pred_class == "fire" else '#4ECDC4'
        prob_color = '#FF6B6B' if prob > 0.5 else '#4ECDC4'
        
        # Bar for probability
        ax_bar = fig.add_subplot(gs[1, i]) if i < 3 else None
        
        if ax_bar:
            ax_bar.barh([0], [prob], color=prob_color, height=0.5)
            ax_bar.set_xlim(0, 1)
            ax_bar.set_xlabel('Fire Probability')
            ax_bar.set_title(name, fontsize=10, fontweight='bold')
            ax_bar.set_yticks([])
            
            # Add text labels
            ax_bar.text(prob/2, 0, f"{prob*100:.1f}%", 
                       ha='center', va='center', color='white', fontweight='bold')
            ax_bar.text(0.5, -0.5, f"Class: {pred_class.upper()}", 
                       ha='center', va='top', fontsize=9)
            ax_bar.text(0.5, -0.8, f"Conf: {confidence*100:.1f}%", 
                       ha='center', va='top', fontsize=8, color='gray')
            
            # Add grid lines
            ax_bar.axvline(x=0.5, color='red', linestyle='--', alpha=0.3)
        
        y_pos += 0.6
    
    # ----- Bottom: Prediction Summary -----
    ax_summary = fig.add_subplot(gs[1, :])
    ax_summary.axis('off')
    
    # Create summary text
    fire_count = sum(1 for p in predictions.values() 
                    if not isinstance(p, dict) or p.get('class') == 'fire')
    total_models = len([p for p in predictions.values() 
                       if not isinstance(p, dict) or 'error' not in p])
    
    if fire_count > total_models / 2:
        summary_color = 'red'
        summary_text = f"⚠️  MAJORITY VOTE: FIRE ({fire_count}/{total_models} models)"
    else:
        summary_color = 'green'
        summary_text = f"✓ MAJORITY VOTE: NO FIRE ({total_models - fire_count}/{total_models} models)"
    
    ax_summary.text(0.5, 0.5, summary_text, 
                   transform=ax_summary.transAxes,
                   fontsize=16, fontweight='bold', 
                   color=summary_color,
                   ha='center', va='center',
                   bbox=dict(boxstyle="round,pad=0.5", facecolor='white', alpha=0.8))
    
    # Save figure
    output_dir = Path("inference_results")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"prediction_{Path(image_path).stem}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"Visualization saved to {output_path}")
    plt.show()

# ============================================================
# Batch inference on multiple images
# ============================================================
def batch_inference(models, image_dir, output_dir="inference_results"):
    """
    Run inference on all images in a directory.
    Useful for testing on multiple unseen images.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    image_files = list(Path(image_dir).glob("*.jpg")) + \
                  list(Path(image_dir).glob("*.png")) + \
                  list(Path(image_dir).glob("*.jpeg"))
    
    results_summary = []
    
    for img_path in image_files:
        logger.info(f"\nProcessing: {img_path.name}")
        predictions = predict_image(models, str(img_path), show_visualization=False)
        
        # Save individual result
        result = {
            "image": img_path.name,
            "predictions": predictions
        }
        results_summary.append(result)
    
    # Create summary visualization
    create_summary_heatmap(results_summary, output_dir)
    
    return results_summary

def create_summary_heatmap(results, output_dir):
    """
    Create a heatmap showing predictions across multiple images.
    Great for thesis to show consistent performance.
    """
    if not results:
        return
    
    # Get model names
    model_names = list(results[0]["predictions"].keys())
    model_names = [m for m in model_names if "error" not in results[0]["predictions"][m]]
    
    # Create matrix of probabilities
    data = []
    image_names = []
    
    for res in results:
        probs = []
        for model in model_names:
            if model in res["predictions"] and "probability" in res["predictions"][model]:
                probs.append(res["predictions"][model]["probability"])
            else:
                probs.append(np.nan)
        data.append(probs)
        image_names.append(res["image"])
    
    data = np.array(data)
    
    # Create heatmap
    fig, ax = plt.subplots(figsize=(12, max(6, len(image_names) * 0.3)))
    
    im = ax.imshow(data, cmap='RdYlGn_r', aspect='auto', vmin=0, vmax=1)
    
    # Set ticks
    ax.set_xticks(np.arange(len(model_names)))
    ax.set_yticks(np.arange(len(image_names)))
    ax.set_xticklabels(model_names, rotation=45, ha='right', fontsize=10)
    ax.set_yticklabels(image_names, fontsize=8)
    
    # Add text annotations
    for i in range(len(image_names)):
        for j in range(len(model_names)):
            if not np.isnan(data[i, j]):
                text = ax.text(j, i, f"{data[i, j]:.2f}",
                             ha="center", va="center", color="black", fontsize=8)
    
    ax.set_title("Model Predictions Across Test Images\n(Red = Fire, Green = No Fire)", 
                fontsize=14, fontweight='bold')
    plt.colorbar(im, label='Fire Probability')
    
    plt.tight_layout()
    plt.savefig(output_dir / "batch_predictions_heatmap.png", dpi=300, bbox_inches='tight')
    plt.close()
    logger.info(f"Batch heatmap saved to {output_dir / 'batch_predictions_heatmap.png'}")

# ============================================================
# Main
# ============================================================
def main():
    """Main inference script."""
    logger.info("Loading models...")
    models = load_models()
    
    if not models:
        logger.error("No models loaded. Please train models first.")
        return
    
    # Test on single image
    test_image = "image_05.jpg"
    if os.path.exists(test_image):
        logger.info(f"\nTesting on: {test_image}")
        predictions = predict_image(models, test_image, show_visualization=True)
        
        # Print summary
        print("\n" + "="*70)
        print("PREDICTION SUMMARY")
        print("="*70)
        for name, pred in predictions.items():
            if "error" not in pred:
                print(f"{name:20} → {pred['class']:10} (prob: {pred['probability']:.3f})")
        print("="*70)
    
    else:
        logger.warning(f"Test image {test_image} not found.")
        logger.info("Testing on a random image from dataset...")
        
        # Try to find a test image from the dataset
        test_dir = Path("prepared_data/test")
        if test_dir.exists():
            fire_images = list((test_dir / "fire").glob("*.jpg")) + list((test_dir / "fire").glob("*.png"))
            if fire_images:
                test_image = str(fire_images[0])
                logger.info(f"Testing on: {test_image}")
                predictions = predict_image(models, test_image, show_visualization=True)
    
    # Optional: Batch inference on directory
    # Uncomment to test on multiple images
    # test_dir = "test_images"
    # if os.path.exists(test_dir):
    #     logger.info("\nRunning batch inference...")
    #     results = batch_inference(models, test_dir)

if __name__ == "__main__":
    main()