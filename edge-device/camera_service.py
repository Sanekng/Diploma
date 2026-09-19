#!/usr/bin/env python3

import json
import logging
import socket
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from picamera2 import Picamera2


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_PATH}"
        )

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


CONFIG = load_config()


# ============================================================
# Logging
# ============================================================

LOG_LEVEL = CONFIG.get(
    "logging",
    {}
).get(
    "level",
    "INFO",
).upper()

logging.basicConfig(
    level=getattr(
        logging,
        LOG_LEVEL,
        logging.INFO,
    ),
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger("edge-service")


# ============================================================
# Helpers
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hostname() -> str:
    return socket.gethostname()


# ============================================================
# Edge Device
# ============================================================

class EdgeDevice:

    def __init__(self, config: Dict[str, Any]):

        self.config = config

        # ----------------------------------------------------
        # Device
        # ----------------------------------------------------

        device_config = config["device"]

        self.device_id = device_config["id"]

        # ----------------------------------------------------
        # Server
        # ----------------------------------------------------

        server = config["server"]

        self.base_url = server["base_url"].rstrip("/")

        self.register_endpoint = server.get(
            "register_endpoint",
            "/api/v1/devices/register",
        )

        self.batch_endpoint = server.get(
            "batch_endpoint",
            "/api/v1/batches",
        )

        self.health_endpoint = server.get(
            "health_endpoint",
            "/api/v1/devices/health",
        )

        self.request_timeout = server.get(
            "request_timeout_seconds",
            15,
        )

        # This MUST contain the same token as:
        # settings.edge_api_token
        self.api_token = server.get(
            "api_token",
            "",
        ).strip()

        if not self.api_token:
            raise ValueError(
                "server.api_token is empty. "
                "Set it to the same value as "
                "settings.edge_api_token on the server."
            )

        # ----------------------------------------------------
        # Capture
        # ----------------------------------------------------

        capture = config["capture"]

        self.image_count = capture.get(
            "images_per_batch",
            5,
        )

        self.interval_seconds = capture.get(
            "interval_seconds",
            5,
        )

        self.resolution = tuple(
            capture.get(
                "resolution",
                [1920, 1080],
            )
        )

        self.jpeg_quality = capture.get(
            "jpeg_quality",
            85,
        )

        self.batch_pause = capture.get(
            "pause_between_batches_seconds",
            600,
        )

        # ----------------------------------------------------
        # Storage
        # ----------------------------------------------------

        storage = config.get(
            "storage",
            {},
        )

        self.image_directory = (
            BASE_DIR
            / storage.get(
                "image_directory",
                "images",
            )
        )

        self.image_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ----------------------------------------------------
        # Health
        # ----------------------------------------------------

        health = config.get(
            "health",
            {},
        )

        self.health_interval = health.get(
            "interval_seconds",
            60,
        )

        # ----------------------------------------------------
        # HTTP session
        # ----------------------------------------------------

        self.session = requests.Session()

        # Every authenticated request sent through this
        # session will contain:
        #
        # Authorization: Bearer <token>
        #
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
            }
        )

        # ----------------------------------------------------
        # Runtime state
        # ----------------------------------------------------

        self.camera: Optional[Picamera2] = None

        self.camera_started = False

        self.last_batch_id: Optional[str] = None

        self.last_health_time = 0.0

        self.registered = False

    # ========================================================
    # URLs
    # ========================================================

    def build_url(
        self,
        endpoint: str,
    ) -> str:

        return (
            self.base_url
            + "/"
            + endpoint.lstrip("/")
        )

    # ========================================================
    # Camera
    # ========================================================

    def initialize_camera(self) -> None:

        logger.info(
            "Initializing Raspberry Pi camera..."
        )

        self.camera = Picamera2()

        camera_config = (
            self.camera.create_still_configuration(
                main={
                    "size": self.resolution,
                    "format": "RGB888",
                }
            )
        )

        self.camera.configure(
            camera_config
        )

        self.camera.start()

        self.camera_started = True

        # Allow sensor to stabilize.
        time.sleep(2)

        logger.info(
            "Camera initialized: %sx%s",
            self.resolution[0],
            self.resolution[1],
        )

    def close_camera(self) -> None:

        if self.camera is None:
            return

        logger.info(
            "Closing camera..."
        )

        try:

            if self.camera_started:
                self.camera.stop()

        except Exception:
            logger.exception(
                "Error while stopping camera."
            )

        try:

            self.camera.close()

        except Exception:
            logger.exception(
                "Error while closing camera."
            )

        self.camera = None
        self.camera_started = False

    # ========================================================
    # Image Capture
    # ========================================================

    def capture_batch(self) -> Dict[str, Any]:

        if (
            self.camera is None
            or not self.camera_started
        ):
            raise RuntimeError(
                "Camera is not initialized."
            )

        batch_id = str(
            uuid.uuid4()
        )

        batch_directory = (
            self.image_directory
            / batch_id
        )

        batch_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        images = []

        logger.info(
            "Starting batch %s (%d images)",
            batch_id,
            self.image_count,
        )

        try:

            for sequence_number in range(
                1,
                self.image_count + 1,
            ):

                filename = (
                    f"image_"
                    f"{sequence_number:02d}"
                    f".jpg"
                )

                image_path = (
                    batch_directory
                    / filename
                )

                captured_at = utc_now()

                logger.info(
                    "Capturing image %d/%d...",
                    sequence_number,
                    self.image_count,
                )

                self.camera.capture_file(
                    str(image_path)
                )

                file_size = (
                    image_path.stat().st_size
                )

                image_metadata = {
                    "image_id": str(
                        uuid.uuid4()
                    ),
                    "sequence_number":
                        sequence_number,
                    "captured_at":
                        captured_at,
                    "filename":
                        filename,
                    "file_size":
                        file_size,
                }

                images.append(
                    {
                        "metadata":
                            image_metadata,
                        "path":
                            image_path,
                    }
                )

                logger.info(
                    "Captured %s (%d bytes)",
                    filename,
                    file_size,
                )

                # Five seconds between photos.
                if (
                    sequence_number
                    < self.image_count
                ):
                    time.sleep(
                        self.interval_seconds
                    )

            batch = {
                "batch_id":
                    batch_id,

                "device_id":
                    self.device_id,

                "hostname":
                    hostname(),

                "created_at":
                    utc_now(),

                "images":
                    images,
            }

            self.last_batch_id = batch_id

            logger.info(
                "Batch %s captured successfully.",
                batch_id,
            )

            return batch

        except Exception:

            # Remove incomplete batch.
            self.remove_batch(
                batch_directory
            )

            raise

    # ========================================================
    # Batch Upload
    # ========================================================

    def send_batch(
        self,
        batch: Dict[str, Any],
    ) -> bool:

        url = self.build_url(
            self.batch_endpoint
        )

        metadata_images = []

        files = []

        logger.info(
            "Uploading batch %s...",
            batch["batch_id"],
        )

        try:

            for image in batch["images"]:

                path = image["path"]

                file_handle = open(
                    path,
                    "rb",
                )

                files.append(
                    (
                        "images",
                        (
                            image["metadata"][
                                "filename"
                            ],
                            file_handle,
                            "image/jpeg",
                        ),
                    )
                )

                metadata_images.append(
                    image["metadata"]
                )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # FastAPI expects:
            #
            # metadata: JSON string
            # images: uploaded files
            #
            # Your original client sent "images" metadata
            # instead of "metadata", which does not match
            # the server endpoint.
            # ------------------------------------------------

            metadata = {
                "batch_id":
                    batch["batch_id"],

                "device_id":
                    batch["device_id"],

                "hostname":
                    batch["hostname"],

                "created_at":
                    batch["created_at"],

                "images":
                    metadata_images,
            }

            response = self.session.post(
                url,
                data={
                    "metadata":
                        json.dumps(metadata)
                },
                files=files,
                timeout=self.request_timeout,
            )

            if response.status_code == 401:

                logger.error(
                    "Batch upload rejected: "
                    "401 Unauthorized. "
                    "Check server edge_api_token."
                )

                return False

            if response.status_code == 403:

                logger.error(
                    "Batch upload rejected: "
                    "403 Forbidden. "
                    "The device may not be registered."
                )

                return False

            response.raise_for_status()

            logger.info(
                "Batch %s uploaded successfully.",
                batch["batch_id"],
            )

            return True

        except requests.RequestException as exc:

            logger.warning(
                "Batch upload failed: %s",
                exc,
            )

            return False

        except Exception:

            logger.exception(
                "Unexpected batch upload error."
            )

            return False

        finally:

            for (
                _,
                (
                    _filename,
                    file_handle,
                    _content_type,
                ),
            ) in files:

                try:
                    file_handle.close()

                except Exception:
                    pass

    # ========================================================
    # Health
    # ========================================================

    def get_camera_health(self) -> str:

        if (
            self.camera is not None
            and self.camera_started
        ):
            return "OK"

        return "NOT_INITIALIZED"

    def get_health_data(
        self,
    ) -> Dict[str, Any]:

        return {
            "device_id":
                self.device_id,

            "hostname":
                hostname(),

            "timestamp":
                utc_now(),

            "status":
                "ONLINE",

            "camera": {
                "status":
                    self.get_camera_health(),

                "resolution": {
                    "width":
                        self.resolution[0],

                    "height":
                        self.resolution[1],
                },
            },

            "last_batch_id":
                self.last_batch_id,
        }

    def send_health(self) -> bool:

        url = self.build_url(
            self.health_endpoint
        )

        try:

            response = self.session.post(
                url,
                json=self.get_health_data(),
                timeout=self.request_timeout,
            )

            if response.status_code == 401:

                logger.error(
                    "Health request rejected: "
                    "401 Unauthorized. "
                    "Check edge API token."
                )

                return False

            response.raise_for_status()

            logger.debug(
                "Health information sent."
            )

            return True

        except requests.RequestException as exc:

            logger.warning(
                "Unable to send health information: %s",
                exc,
            )

            return False

    def wait_between_batches(self) -> None:
        """
        Wait between batches while continuing to send periodic
        health updates instead of blocking for one long sleep.
        """

        end_time = time.monotonic() + self.batch_pause

        while True:

            now = time.monotonic()

            if now >= end_time:
                break

            if (
                now
                - self.last_health_time
                >= self.health_interval
            ):

                self.send_health()
                self.last_health_time = now

            time.sleep(1)

    # ========================================================
    # Registration
    # ========================================================

    def register(self) -> bool:

        url = self.build_url(
            self.register_endpoint
        )

        payload = {
            "device_id":
                self.device_id,

            "hostname":
                hostname(),

            "device_type":
                "raspberry_pi",

            "camera": {
                "model":
                    "OV5647",

                "resolution": {
                    "width":
                        self.resolution[0],

                    "height":
                        self.resolution[1],
                },
            },
        }

        logger.info(
            "Registering device %s...",
            self.device_id,
        )

        try:

            response = self.session.post(
                url,
                json=payload,
                timeout=self.request_timeout,
            )

            if response.status_code == 401:

                logger.error(
                    "Registration rejected: "
                    "401 Unauthorized."
                )

                logger.error(
                    "The token in config.json does not "
                    "match settings.edge_api_token."
                )

                return False

            response.raise_for_status()

            self.registered = True

            logger.info(
                "Device registered successfully."
            )

            return True

        except requests.RequestException as exc:

            logger.warning(
                "Device registration failed: %s",
                exc,
            )

            return False

    # ========================================================
    # Remove Local Batch
    # ========================================================

    def remove_batch(
        self,
        batch_directory: Path,
    ) -> None:

        try:

            if batch_directory.exists():

                for path in batch_directory.iterdir():

                    try:
                        path.unlink()

                    except Exception:
                        pass

                batch_directory.rmdir()

        except Exception:

            logger.warning(
                "Could not remove local batch: %s",
                batch_directory,
            )

    # ========================================================
    # Main Loop
    # ========================================================

    def run(self) -> None:

        logger.info(
            "========================================"
        )

        logger.info(
            "Starting Edge Device"
        )

        logger.info(
            "Device ID: %s",
            self.device_id,
        )

        logger.info(
            "Server: %s",
            self.base_url,
        )

        logger.info(
            "========================================"
        )

        # ----------------------------------------------------
        # Camera
        # ----------------------------------------------------

        self.initialize_camera()

        # ----------------------------------------------------
        # Registration
        # ----------------------------------------------------

        while not self.registered:

            if self.register():

                break

            logger.warning(
                "Registration failed. "
                "Retrying in 10 seconds..."
            )

            time.sleep(10)

        # ----------------------------------------------------
        # Initial health
        # ----------------------------------------------------

        self.send_health()

        self.last_health_time = (
            time.monotonic()
        )

        # ----------------------------------------------------
        # Main loop
        # ----------------------------------------------------

        while True:

            try:

                current_time = (
                    time.monotonic()
                )

                # --------------------------------------------
                # Health
                # --------------------------------------------

                if (
                    current_time
                    - self.last_health_time
                    >= self.health_interval
                ):

                    self.send_health()

                    self.last_health_time = (
                        current_time
                    )

                # --------------------------------------------
                # Capture
                # --------------------------------------------

                batch = (
                    self.capture_batch()
                )

                # --------------------------------------------
                # Upload
                # --------------------------------------------

                uploaded = (
                    self.send_batch(
                        batch
                    )
                )

                if uploaded:

                    # Once successfully uploaded,
                    # local files are no longer required.
                    batch_directory = (
                        self.image_directory
                        / batch["batch_id"]
                    )

                    self.remove_batch(
                        batch_directory
                    )

                else:

                    logger.warning(
                        "Batch %s was not uploaded. "
                        "Keeping local files.",
                        batch["batch_id"],
                    )

                # --------------------------------------------
                # Pause before next batch
                # --------------------------------------------

                logger.info(
                    "Waiting %s seconds before "
                    "next batch.",
                    self.batch_pause,
                )

                self.wait_between_batches()

            except KeyboardInterrupt:

                logger.info(
                    "Shutdown requested."
                )

                break

            except Exception:

                logger.exception(
                    "Unexpected error in edge service."
                )

                # Try to keep the service alive.
                time.sleep(10)

        self.close_camera()


# ============================================================
# Entry Point
# ============================================================

def main():

    device = EdgeDevice(
        CONFIG
    )

    try:

        device.run()

    except KeyboardInterrupt:

        logger.info(
            "Service stopped."
        )

    finally:

        device.close_camera()


if __name__ == "__main__":
    main()