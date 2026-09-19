import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .config import settings


logger = logging.getLogger("dbs.database")


client = MongoClient(
    settings.mongodb_url,
    serverSelectionTimeoutMS=5000,
)

database: Database = client[
    settings.mongodb_database
]


devices_collection = database[
    "devices"
]

batches_collection = database[
    "batches"
]

logs_collection = database[
    "logs"
]


def initialize_database() -> None:

    logger.info(
        "Initializing MongoDB indexes..."
    )

    # --------------------------------------------------------
    # Devices
    # --------------------------------------------------------

    devices_collection.create_index(
        [
            ("device_id", ASCENDING)
        ],
        unique=True,
        name="device_id_unique",
    )

    devices_collection.create_index(
        [
            ("last_seen_at", DESCENDING)
        ],
        name="last_seen_at_index",
    )

    # --------------------------------------------------------
    # Batches
    # --------------------------------------------------------

    batches_collection.create_index(
        [
            ("batch_id", ASCENDING)
        ],
        unique=True,
        name="batch_id_unique",
    )

    batches_collection.create_index(
        [
            ("device_id", ASCENDING),
            ("created_at", DESCENDING),
        ],
        name="device_batches_index",
    )

    batches_collection.create_index(
        [
            ("status", ASCENDING),
            ("created_at", DESCENDING),
        ],
        name="batch_status_index",
    )

    # --------------------------------------------------------
    # Logs
    # --------------------------------------------------------

    logs_collection.create_index(
        [
            ("created_at", DESCENDING)
        ],
        name="logs_created_at_index",
    )

    logs_collection.create_index(
        [
            ("device_id", ASCENDING),
            ("created_at", DESCENDING),
        ],
        name="device_logs_index",
    )

    logger.info(
        "MongoDB indexes initialized."
    )


def ping_database() -> bool:

    try:

        client.admin.command(
            "ping"
        )

        return True

    except Exception as exc:

        logger.error(
            "MongoDB ping failed: %s",
            exc,
        )

        return False