from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fire Detection - Main Control Service"
    app_version: str = "0.1.0"

    host: str = "0.0.0.0"
    port: int = 3000

    # Other services
    ias_url: str = "http://ias:8001"
    dbs_url: str = "http://dbs:8002"
    wds_url: str = "http://wds:8003"

    # Edge authentication
    edge_api_token: str = "change-me-to-a-real-secret"

    # Network settings
    request_timeout_seconds: int = 30

    # Health
    device_offline_after_seconds: int = 300

    device_health_check_interval_seconds: int = 30

    # Retention
    batches_to_keep_per_device: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()