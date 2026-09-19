import logging
from typing import Any, Dict, Optional


logger = logging.getLogger("mcs")


def log_event(
    level: str,
    event: str,
    message: str,
    device_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    extra = {
        "event": event,
        "device_id": device_id,
        "batch_id": batch_id,
        "metadata": metadata or {},
    }

    log_method = getattr(
        logger,
        level.lower(),
        logger.info,
    )

    log_method(
        message,
        extra=extra,
    )