from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fire Detection Database Service"
    app_version: str = "0.1.0"

    host: str = "0.0.0.0"
    port: int = 8002

    mongodb_url: str = (
        "mongodb://mongodb:27017"
    )

    mongodb_database: str = "fire_detection"

    # Maximum number of completed batches retained
    # for each edge device.
    batches_to_keep_per_device: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()