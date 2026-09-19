from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class BatchStatus(str, Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Prediction(str, Enum):
    FIRE = "FIRE"
    NON_FIRE = "NON_FIRE"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================================================
# DEVICE
# ============================================================

class RegisterDeviceRequest(BaseModel):

    device_id: str = Field(
        min_length=1,
        max_length=128,
    )

    hostname: str

    latitude: Optional[float] = None

    longitude: Optional[float] = None

    firmware_version: Optional[str] = None

    camera_model: Optional[str] = None

    registered_at: datetime

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


class UpdateDeviceHealthRequest(BaseModel):

    status: DeviceStatus

    timestamp: datetime

    cpu_usage_percent: Optional[float] = None

    memory_usage_percent: Optional[float] = None

    temperature_celsius: Optional[float] = None

    disk_usage_percent: Optional[float] = None

    camera_available: Optional[bool] = None

    uptime_seconds: Optional[float] = None

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


# ============================================================
# IMAGES
# ============================================================

class BatchImage(BaseModel):

    image_id: str

    sequence_number: int

    filename: str

    captured_at: datetime

    storage_path: str

    file_size: Optional[int] = None


# ============================================================
# BATCH
# ============================================================

class CreateBatchRequest(BaseModel):

    batch_id: str

    device_id: str

    hostname: str

    created_at: datetime

    images: List[BatchImage]


class UpdateBatchResultRequest(BaseModel):

    status: BatchStatus

    prediction: Optional[Prediction] = None

    confidence: Optional[float] = None

    model_id: Optional[str] = None

    model_version: Optional[str] = None

    image_predictions: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    analyzed_at: Optional[datetime] = None

    error: Optional[str] = None


class CleanupBatchesRequest(BaseModel):

    device_id: str

    keep: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
    )


# ============================================================
# LOGS
# ============================================================

class CreateLogRequest(BaseModel):

    level: LogLevel

    service: str

    message: str

    device_id: Optional[str] = None

    batch_id: Optional[str] = None

    created_at: datetime

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )