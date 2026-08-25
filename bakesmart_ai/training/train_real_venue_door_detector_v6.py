"""Train the corrected, self-diagnosing v6 Door detector.

This version requires the confirmed real-venue-0038 label correction, performs
a short predictor warmup, adapts TorchVision's remaining trainable detector
layers, calibrates confidence on validation, and aborts at epoch five if it
cannot detect a Door in known-positive training scenes.
"""

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


DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_door_detector_v6"
DOOR_PROFILE_V6 = ObjectDetectorProfile(
    class_id=2,
    class_key="door",
    display_name="Door",
    model_name="BakeSmartDoorDetectorV6",
    title="BakeSmart Step 4 v6 — Corrected Self-Diagnosing Door Detector",
    minimum_training_scenes=5,
    adaptive_fine_tuning=True,
    forbidden_positive_scene_ids=("real-venue-0038",),
)


def main() -> int:
    parser = build_parser()
    parser.description = __doc__
    parser.set_defaults(
        output_dir=str(DEFAULT_OUTPUT_DIR),
        seed=260831,
        epochs=20,
        patience=6,
        focus_repeats=3,
        minimum_image_size=384,
        maximum_image_size=640,
        learning_rate=2e-3,
        rpn_learning_rate=5e-4,
        weight_decay=5e-4,
        grad_clip=5.0,
        warmup_epochs=2,
        probe_epoch=5,
        probe_scenes=3,
    )
    if "BAKESMART_TORCH_THREADS" in os.environ:
        torch.set_num_threads(max(1, int(os.environ["BAKESMART_TORCH_THREADS"])))
    try:
        train(parser.parse_args(), profile=DOOR_PROFILE_V6)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
