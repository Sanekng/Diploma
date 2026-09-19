# Repository setup

This repository contains the application source, service definitions, Docker configuration, and training code. Large image collections and runtime files are deliberately kept outside normal Git history.

## Files excluded from Git

- `data/`: source fire and non-fire training images.
- `test-images/`: local test image inputs.
- `training/prepared_data/`: generated training data.
- `training/results/`: generated training outputs.
- `*.keras`: trained model binaries, which are too large for regular GitHub files.
- `storage/`: captured batches and service runtime files. The directory itself is retained with `storage/.gitkeep`.
- Python virtual environments, caches, local databases, and secret configuration.

## Keeping the training images

GitHub repositories are not suitable for this project's multi-gigabyte image collections. Keep `data/`, `test-images/`, and any generated training artifacts in external object storage or a dataset registry, with versioned archives and checksums. Suitable options include an institutional cloud drive, S3-compatible storage, Google Drive, or Hugging Face Datasets. Restore the folders at the paths above before running `training/train.py`.

Do not commit a large archive as a workaround: GitHub has per-file and repository size limits, and Git history retains deleted large files. Git LFS is an option only when the hosting account has enough LFS storage and bandwidth, so it should be agreed separately rather than assumed.

The IAS service expects its model at `services/ias/models/fire_detection_model.keras`. Keep that model, and the training models under `training/models/`, in the same external artifact storage. Restore them at their original paths before starting IAS or running model evaluation.

## Before the first push

1. Restore the external dataset if training is required.
2. Review `git status --ignored` and confirm no `.env` files, virtual environments, image data, or `storage/` contents are staged.
3. Add the GitHub remote and push the source repository.
