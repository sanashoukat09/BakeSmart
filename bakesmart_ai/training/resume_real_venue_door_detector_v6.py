"""Resume the valid v6 Door checkpoint with lower, guarded learning rates."""

from __future__ import annotations

import os
import sys

import torch

from training.annotation_workspace import PROJECT_DIR
from training.train_real_venue_door_detector_v6 import DOOR_PROFILE_V6
from training.train_real_venue_outlet_detector_v5 import build_parser, train


OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_door_detector_v6"
CHECKPOINT = OUTPUT_DIR / "best_model.pt"


def main() -> int:
    parser = build_parser()
    parser.description = __doc__
    parser.set_defaults(
        output_dir=str(OUTPUT_DIR),
        resume_checkpoint=str(CHECKPOINT),
        seed=260831,
        epochs=20,
        patience=6,
        focus_repeats=3,
        minimum_image_size=384,
        maximum_image_size=640,
        learning_rate=4e-4,
        rpn_learning_rate=1e-4,
        weight_decay=5e-4,
        grad_clip=2.0,
        warmup_epochs=2,
        probe_epoch=5,
        probe_scenes=3,
        max_nonfinite_skips=3,
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
