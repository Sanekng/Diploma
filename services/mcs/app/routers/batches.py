import json
import shutil
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)

from ..config import settings
from ..models import BatchMetadata
from ..services import process_batch
from ..state import get_device
from ..auth import verify_edge_token


router = APIRouter(
    prefix="/api/v1/batches",
    tags=["batches"],
)


STORAGE_PATH = Path(
    "/app/storage"
)

STORAGE_PATH.mkdir(
    parents=True,
    exist_ok=True,
)

@router.post(
    "",
    dependencies=[Depends(verify_edge_token)],
)
async def receive_batch(
    metadata: str = Form(...),
    images: list[UploadFile] = File(...),
):

    # --------------------------------------------------------
    # Parse metadata
    # --------------------------------------------------------

    try:

        parsed_metadata = json.loads(
            metadata
        )

        batch = BatchMetadata.model_validate(
            parsed_metadata
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=f"Invalid batch metadata: {exc}",
        )

    # --------------------------------------------------------
    # Device validation
    # --------------------------------------------------------

    device = get_device(
        batch.device_id
    )

    if not device:

        raise HTTPException(
            status_code=403,
            detail=(
                "Device is not registered. "
                "Register the device first."
            ),
        )

    # --------------------------------------------------------
    # Validate number of images
    # --------------------------------------------------------

    if len(images) != len(batch.images):

        raise HTTPException(
            status_code=400,
            detail=(
                "Number of uploaded images "
                "does not match metadata."
            ),
        )

    if len(images) != 5:

        raise HTTPException(
            status_code=400,
            detail=(
                "MVP requires exactly 5 images "
                "per batch."
            ),
        )

    # --------------------------------------------------------
    # Validate image names
    # --------------------------------------------------------

    metadata_by_filename = {
        image.filename: image
        for image in batch.images
    }

    batch_directory = (
        STORAGE_PATH
        / batch.device_id
        / batch.batch_id
    )

    batch_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    saved_images = []

    try:

        for upload in images:

            if not upload.filename:
                raise HTTPException(
                    status_code=400,
                    detail="Image has no filename.",
                )

            if (
                upload.filename
                not in metadata_by_filename
            ):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unexpected image: "
                        f"{upload.filename}"
                    ),
                )

            # Avoid trusting arbitrary client paths.
            safe_filename = Path(
                upload.filename
            ).name

            destination = (
                batch_directory
                / safe_filename
            )

            with open(
                destination,
                "wb",
            ) as output:

                shutil.copyfileobj(
                    upload.file,
                    output,
                )

            saved_images.append(
                {
                    "image_id": metadata_by_filename[
                        upload.filename
                    ].image_id,

                    "sequence_number":
                        metadata_by_filename[
                            upload.filename
                        ].sequence_number,

                    "captured_at":
                        metadata_by_filename[
                            upload.filename
                        ].captured_at.isoformat(),

                    "filename":
                        safe_filename,

                    "storage_path":
                        str(
                            destination.relative_to(
                                STORAGE_PATH
                            )
                        ),

                    "file_size":
                        destination.stat().st_size,
                }
            )

    except Exception:

        shutil.rmtree(
            batch_directory,
            ignore_errors=True,
        )

        raise

    # --------------------------------------------------------
    # Create internal batch object
    # --------------------------------------------------------

    internal_batch = {
        "batch_id": batch.batch_id,
        "device_id": batch.device_id,
        "hostname": batch.hostname,
        "created_at": batch.created_at.isoformat(),
        "images": saved_images,
    }

    # --------------------------------------------------------
    # Start processing
    # --------------------------------------------------------

    result = await process_batch(
        internal_batch
    )

    return {
        "success": True,
        **result,
    }