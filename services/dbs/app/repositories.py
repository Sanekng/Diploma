from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING

from .config import settings
from .database import (
    batches_collection,
    devices_collection,
    logs_collection,
)
from .models import BatchStatus


# ============================================================
# HELPERS
# ============================================================

def serialize(document: Optional[Dict[str, Any]]):

    if document is None:
        return None

    document.pop(
        "_id",
        None,
    )

    return document


# ============================================================
# DEVICES
# ============================================================

def register_device(
    data: Dict[str, Any]
) -> Dict[str, Any]:

    device_id = data[
        "device_id"
    ]

    existing = devices_collection.find_one(
        {
            "device_id": device_id
        }
    )

    if existing:

        # Registration is idempotent.
        # Update basic information instead of
        # creating another device.
        devices_collection.update_one(
            {
                "device_id": device_id
            },
            {
                "$set": {
                    "hostname": data[
                        "hostname"
                    ],

                    "latitude": data.get(
                        "latitude"
                    ),

                    "longitude": data.get(
                        "longitude"
                    ),

                    "firmware_version": data.get(
                        "firmware_version"
                    ),

                    "camera_model": data.get(
                        "camera_model"
                    ),

                    "last_registration_at": data[
                        "registered_at"
                    ],

                    "metadata": data.get(
                        "metadata",
                        {},
                    ),
                }
            },
        )

    else:

        document = {
            **data,

            "status": "UNKNOWN",

            "last_seen_at": None,

            "last_health": None,

            "last_batch_id": None,

            "last_image": None,
        }

        devices_collection.insert_one(
            document
        )

    result = devices_collection.find_one(
        {
            "device_id": device_id
        }
    )

    return serialize(result)


def get_device(
    device_id: str
):

    return serialize(
        devices_collection.find_one(
            {
                "device_id": device_id
            }
        )
    )


def get_devices(
    skip: int = 0,
    limit: int = 100,
):

    cursor = (
        devices_collection
        .find({})
        .sort(
            "device_id",
            1,
        )
        .skip(skip)
        .limit(limit)
    )

    return [
        serialize(document)
        for document in cursor
    ]


def update_device_health(
    device_id: str,
    health: Dict[str, Any],
):

    update = {
        "$set": {
            "status": health[
                "status"
            ],

            "last_health": health,
        }
    }

    if health["status"] != "OFFLINE":
        update["$set"]["last_seen_at"] = health[
            "timestamp"
        ]

    devices_collection.update_one(
        {
            "device_id": device_id
        },
        update,
    )

    result = devices_collection.find_one(
        {
            "device_id": device_id
        }
    )

    return serialize(result)


# ============================================================
# BATCHES
# ============================================================

def create_batch(
    data: Dict[str, Any]
):

    document = {
        **data,

        "status": BatchStatus.RECEIVED.value,

        "prediction": None,

        "confidence": None,

        "model_id": None,

        "model_version": None,

        "image_predictions": [],

        "analyzed_at": None,

        "error": None,

        "completed_at": None,
    }

    batches_collection.insert_one(
        document
    )

    # Update device's latest batch/image.
    last_image = None

    if data.get("images"):

        last_image = data[
            "images"
        ][-1]

    devices_collection.update_one(
        {
            "device_id": data[
                "device_id"
            ]
        },
        {
            "$set": {
                "last_batch_id": data[
                    "batch_id"
                ],

                "last_image": last_image,
            }
        },
    )

    return serialize(
        batches_collection.find_one(
            {
                "batch_id": data[
                    "batch_id"
                ]
            }
        )
    )


def get_batch(
    batch_id: str
):

    return serialize(
        batches_collection.find_one(
            {
                "batch_id": batch_id
            }
        )
    )


def update_batch_result(
    batch_id: str,
    result: Dict[str, Any],
):

    update = {
        "status": result[
            "status"
        ],

        "prediction": result.get(
            "prediction"
        ),

        "confidence": result.get(
            "confidence"
        ),

        "model_id": result.get(
            "model_id"
        ),

        "model_version": result.get(
            "model_version"
        ),

        "image_predictions": result.get(
            "image_predictions",
            [],
        ),

        "analyzed_at": result.get(
            "analyzed_at"
        ),

        "error": result.get(
            "error"
        ),
    }

    if result["status"] in (
        BatchStatus.COMPLETED.value,
        BatchStatus.FAILED.value,
    ):

        update[
            "completed_at"
        ] = datetime.utcnow()

    batches_collection.update_one(
        {
            "batch_id": batch_id
        },
        {
            "$set": update
        },
    )

    return get_batch(
        batch_id
    )


def get_device_batches(
    device_id: str,
    limit: int = 3,
):

    cursor = (
        batches_collection
        .find(
            {
                "device_id": device_id
            }
        )
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(limit)
    )

    return [
        serialize(document)
        for document in cursor
    ]


def get_latest_batches(
    limit: int = 50,
):

    cursor = (
        batches_collection
        .find({})
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(limit)
    )

    return [
        serialize(document)
        for document in cursor
    ]


def delete_old_batches_for_device(
    device_id: str,
    keep: Optional[int] = None,
):

    keep_count = (
        keep
        if keep is not None
        else settings.batches_to_keep_per_device
    )

    batches = list(
        batches_collection
        .find(
            {
                "device_id": device_id
            },
            {
                "_id": 1
            },
        )
        .sort(
            "created_at",
            DESCENDING,
        )
        .skip(
            keep_count
        )
    )

    ids = [
        batch["_id"]
        for batch in batches
    ]

    if not ids:
        return 0

    result = (
        batches_collection
        .delete_many(
            {
                "_id": {
                    "$in": ids
                }
            }
        )
    )

    return result.deleted_count


def cleanup_all_devices():

    device_ids = (
        devices_collection
        .distinct(
            "device_id"
        )
    )

    deleted = 0

    for device_id in device_ids:

        deleted += (
            delete_old_batches_for_device(
                device_id
            )
        )

    return deleted


# ============================================================
# LOGS
# ============================================================

def create_log(
    data: Dict[str, Any]
):

    result = logs_collection.insert_one(
        data
    )

    document = logs_collection.find_one(
        {
            "_id": result.inserted_id
        }
    )

    return serialize(
        document
    )


def get_logs(
    device_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    limit: int = 100,
):

    query: Dict[str, Any] = {}

    if device_id:
        query[
            "device_id"
        ] = device_id

    if batch_id:
        query[
            "batch_id"
        ] = batch_id

    cursor = (
        logs_collection
        .find(query)
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(limit)
    )

    return [
        serialize(document)
        for document in cursor
    ]