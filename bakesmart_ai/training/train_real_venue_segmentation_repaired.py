"""Train a fresh segmentation model on corrected real_v2 train/validation labels.

Run ``training.prepare_repaired_real_venue_dataset`` first. This trainer uses
the preserved split membership, refuses any manifest other than
``real_v2_repaired``, and never requests the locked test split.
"""

from __future__ import annotations

import os
import sys

import torch

from training.annotation_workspace import PROJECT_DIR
from training.train_real_venue_segmentation_v3 import (
    TrainingProfile,
    build_parser,
    train,
)


DEFAULT_MANIFEST = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
    / "splits" / "split_manifest.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_real_repaired_v1"
PROFILE = TrainingProfile(
    title="BakeSmart Step 4 repaired — Corrected Venue Segmentation",
    expected_dataset="real_v2_repaired",
    schema_version=4,
    training_variant="balanced_corrected_labels_v4",
    training_data="corrected_real_v2_repaired_train_split_only",
    validation_data="corrected_real_v2_repaired_validation_split_only",
    result_heading="Best corrected-label validation result",
    prior_outputs_message="v1, v2 and v3 outputs remain untouched.",
    next_step="compare validation results, then freeze one model before using the locked test",
)


def main() -> int:
    parser = build_parser()
    parser.set_defaults(
        manifest=str(DEFAULT_MANIFEST),
        output_dir=str(DEFAULT_OUTPUT_DIR),
        seed=260826,
    )
    args = parser.parse_args()
    if "BAKESMART_TORCH_THREADS" in os.environ:
        torch.set_num_threads(max(1, int(os.environ["BAKESMART_TORCH_THREADS"])))
    try:
        train(args, profile=PROFILE)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
