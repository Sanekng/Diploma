from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Fire Detection - Image Analysis Service"
    app_version: str = "0.1.0"

    host: str = "0.0.0.0"
    port: int = 8001

    # Model
    model_id: str = "fire-detection-resnet50"
    model_version: str = "1.0.0"

    model_path: str = str(
        BASE_DIR / "models" / "fire_detection_model.keras"
    )

    # Dataset
    data_path: str = str(
        BASE_DIR / "data"
    )

    # Image configuration
    image_width: int = 224
    image_height: int = 224

    # Prediction
    fire_threshold: float = 0.65

    # Batch configuration
    expected_images_per_batch: int = 5

    # Shared storage.
    # MCS and IAS must mount the same host directory.
    storage_path: str = "/app/storage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()