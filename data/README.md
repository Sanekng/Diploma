# Training data

The image dataset is intentionally excluded from Git. The local dataset currently lives in `data/fire/` and `data/non-fire/` and is used by the training scripts.

Store a copy in external object storage or a dataset registry, then restore those directories before running training. Do not commit image datasets or generated archives to the main repository.
