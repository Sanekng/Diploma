from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    WARNING = "WARNING"


class CameraStatus(str, Enum):
    OK = "OK"
    NOT_INITIALIZED = "NOT_INITIALIZED"
    ERROR = "ERROR"


class BatchStatus(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Prediction(str, Enum):
    FIRE = "FIRE"
    NON_FIRE = "NON_FIRE"
    UNKNOWN = "UNKNOWN"


class DeviceLocation(BaseModel):
    latitude: float
    longitude: float


class CameraInfo(BaseModel):
    model: str = "OV5647"
    resolution: Dict[str, int]


class DeviceRegistrationRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    hostname: str
    device_type: str = "raspberry_pi"
    camera: CameraInfo
    location: Optional[DeviceLocation] = None


class DeviceHealthRequest(BaseModel):
    device_id: str
    hostname: str
    timestamp: datetime
    status: str = "ONLINE"

    camera: Dict[str, Any]

    last_batch_id: Optional[str] = None


class ImageMetadata(BaseModel):
    image_id: str
    sequence_number: int = Field(ge=1, le=100)
    captured_at: datetime
    filename: str
    file_size: int = Field(ge=1)


class BatchMetadata(BaseModel):
    batch_id: str
    device_id: str
    hostname: str
    created_at: datetime
    images: List[ImageMetadata]


class AnalysisResult(BaseModel):
    batch_id: str
    device_id: str

    prediction: Prediction
    confidence: float = Field(ge=0.0, le=1.0)

    model_id: Optional[str] = None
    model_version: Optional[str] = None

    image_predictions: Optional[List[Dict[str, Any]]] = None

    analyzed_at: datetime


class BatchResult(BaseModel):
    batch_id: str
    status: BatchStatus

    prediction: Optional[Prediction] = None
    confidence: Optional[float] = None

    model_id: Optional[str] = None
    model_version: Optional[str] = None

    error: Optional[str] = None