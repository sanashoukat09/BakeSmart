"""Train the v5 dedicated Door detector on corrected development labels."""

from __future__ import annotations

import os
import sys

import torch

from training.annotation_workspace import PROJECT_DIR
from training.train_real_venue_outlet_detector_v5 import (
    ObjectDetectorProfile,
    build_parser,
    train,
)


DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_door_detector_v5"
DOOR_PROFILE = ObjectDetectorProfile(
    class_id=2,
    class_key="door",
    display_name="Door",
    model_name="BakeSmartDoorDetector",
    title="BakeSmart Step 4 v5 — Dedicated Door Detector",
    minimum_training_scenes=5,
)


def main() -> int:
    parser = build_parser()
    parser.description = __doc__
    parser.set_defaults(
        output_dir=str(DEFAULT_OUTPUT_DIR),
        seed=260830,
        epochs=30,
        patience=10,
        focus_repeats=5,
    )
    if "BAKESMART_TORCH_THREADS" in os.environ:
        torch.set_num_threads(max(1, int(os.environ["BAKESMART_TORCH_THREADS"])))
    try:
        train(parser.parse_args(), profile=DOOR_PROFILE)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
