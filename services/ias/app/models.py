from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Prediction(str, Enum):
    FIRE = "FIRE"
    NON_FIRE = "NON_FIRE"


class ImageInput(BaseModel):
    image_id: str
    sequence_number: int = Field(
        ge=1,
        le=100,
    )
    captured_at: datetime
    filename: str

    # Relative path inside shared storage.
    storage_path: str

    file_size: Optional[int] = None


class AnalyzeBatchRequest(BaseModel):
    batch_id: str
    device_id: str
    hostname: str

    created_at: datetime

    images: List[ImageInput]


class ImagePrediction(BaseModel):
    image_id: str
    sequence_number: int
    filename: str

    fire_probability: float
    prediction: Prediction


class AnalyzeBatchResponse(BaseModel):
    batch_id: str
    device_id: str

    prediction: Prediction
    confidence: float

    model_id: str
    model_version: str

    image_predictions: List[ImagePrediction]

    analyzed_at: datetime