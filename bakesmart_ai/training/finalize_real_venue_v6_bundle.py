"""Package the validated v5 room model and v6 Door model for local inference.

This command does not train, inspect the locked test split, or claim production
approval. It verifies the existing validation reports and checkpoints, strips
training-only optimizer state, and creates one validation-only runtime bundle.
Outlets deliberately remain customer-marked because the development set has too
few positive Outlet scenes for a reliable automatic detector.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import torch

from training.annotation_workspace import PROJECT_DIR
from training.real_venue_segmentation import sha256_file
from training.train_real_venue_segmentation_v2 import utc_now


DEFAULT_SEGMENTATION_DIR = PROJECT_DIR / "models" / "venue_vision_real_v5"
DEFAULT_DOOR_DIR = PROJECT_DIR / "models" / "venue_vision_door_detector_v6"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_bundle_v6"
MODEL_VERSION = "venue-vision-v6-validation-bundle"


def _load_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a JSON object")
    return payload


def _load_checkpoint(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be a dictionary")
    if not isinstance(payload.get("model_state_dict"), dict):
        raise ValueError(f"{label} has no model_state_dict")
    if payload.get("test_data_used") is not False:
        raise ValueError(f"{label} must confirm test_data_used=false")
    return payload


def _metric(metrics: object, key: str, label: str) -> float:
    if not isinstance(metrics, dict) or not isinstance(metrics.get(key), (int, float)):
        raise ValueError(f"{label} has no numeric {key}")
    return float(metrics[key])


def _verify_report(
    report: dict[str, object],
    checkpoint: dict[str, object],
    checkpoint_path: Path,
    *,
    expected_model: str,
    label: str,
) -> None:
    if report.get("model_name") != expected_model:
        raise ValueError(f"{label} report model is not {expected_model}")
    if checkpoint.get("model_name") != expected_model:
        raise ValueError(f"{label} checkpoint model is not {expected_model}")
    if report.get("test_split_used") is not False:
        raise ValueError(f"{label} report must confirm test_split_used=false")
    if report.get("production_ready") is not False:
        raise ValueError(f"{label} report must remain production_ready=false")
    if report.get("checkpoint_sha256") != sha256_file(checkpoint_path):
        raise ValueError(f"{label} checkpoint checksum does not match its report")
    if report.get("split_manifest_sha256") != checkpoint.get("manifest_sha256"):
        raise ValueError(f"{label} report/checkpoint split hashes do not match")


def _write_compact_checkpoint(
    destination: Path,
    checkpoint: dict[str, object],
    *,
    keep: tuple[str, ...],
) -> None:
    payload = {key: checkpoint[key] for key in keep if key in checkpoint}
    payload["model_state_dict"] = checkpoint["model_state_dict"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    torch.save(payload, temporary)
    temporary.replace(destination)


def finalize(
    *,
    segmentation_dir: Path,
    door_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    segmentation_dir = segmentation_dir.resolve()
    door_dir = door_dir.resolve()
    output_dir = output_dir.resolve()
    segmentation_path = segmentation_dir / "best_model.pt"
    door_path = door_dir / "best_model.pt"
    segmentation_report = _load_json(
        segmentation_dir / "validation_report.json", "v5 segmentation report"
    )
    door_report = _load_json(door_dir / "validation_report.json", "v6 Door report")
    segmentation = _load_checkpoint(segmentation_path, "v5 segmentation checkpoint")
    door = _load_checkpoint(door_path, "v6 Door checkpoint")
    _verify_report(
        segmentation_report,
        segmentation,
        segmentation_path,
        expected_model="BakeSmartLRASPP",
        label="v5 segmentation",
    )
    _verify_report(
        door_report,
        door,
        door_path,
        expected_model="BakeSmartDoorDetectorV6",
        label="v6 Door",
    )

    segmentation_metrics = segmentation_report.get("best_validation_metrics")
    mean_iou = _metric(segmentation_metrics, "mean_iou", "v5 validation metrics")
    pixel_accuracy = _metric(
        segmentation_metrics, "pixel_accuracy", "v5 validation metrics"
    )
    door_metrics = door_report.get("best_validation_metrics")
    calibrated_f1 = _metric(door_metrics, "calibrated_f1", "v6 Door metrics")
    mean_best_iou = _metric(door_metrics, "mean_best_iou", "v6 Door metrics")
    threshold = _metric(
        door_metrics, "calibrated_score_threshold", "v6 Door metrics"
    )
    validation_positive_count = int(door_report.get("validation_positive_scene_count") or 0)
    if mean_iou < 0.35 or pixel_accuracy < 0.70:
        raise ValueError(
            "v5 room checkpoint is below the validation-only runtime guard "
            "(mIoU >= 0.35 and pixel accuracy >= 0.70)"
        )
    if calibrated_f1 < 0.50 or mean_best_iou < 0.50 or validation_positive_count < 2:
        raise ValueError(
            "v6 Door checkpoint is below the validation-only runtime guard "
            "(calibrated F1/IoU >= 0.50 and at least two positive validation scenes)"
        )
    if not 0.01 <= threshold <= 0.90:
        raise ValueError("v6 Door calibrated threshold is outside the safe range")

    output_dir.mkdir(parents=True, exist_ok=True)
    segmentation_output = output_dir / "segmentation_model.pt"
    door_output = output_dir / "door_model.pt"
    _write_compact_checkpoint(
        segmentation_output,
        segmentation,
        keep=(
            "schema_version",
            "model_name",
            "architecture",
            "num_classes",
            "class_names",
            "test_data_used",
            "manifest_sha256",
            "epoch",
            "validation_metrics",
            "config",
        ),
    )
    _write_compact_checkpoint(
        door_output,
        door,
        keep=(
            "schema_version",
            "model_name",
            "architecture",
            "num_classes",
            "class_names",
            "test_data_used",
            "manifest_sha256",
            "epoch",
            "validation_metrics",
        ),
    )

    manifest: dict[str, object] = {
        "schema_version": 6,
        "created_at_utc": utc_now(),
        "model_version": MODEL_VERSION,
        "status": "validation_only_unconfirmed_runtime",
        "production_ready": False,
        "locked_test_used": False,
        "automatic_classes": ["wall", "floor", "window", "furniture", "door", "walkway"],
        "manual_classes": ["outlet"],
        "runtime_policy": {
            "all_candidates_require_customer_confirmation": True,
            "maximum_reported_confidence": 0.49,
            "door_score_threshold": threshold,
            "outlet_mode": "customer_manual",
            "segmentation_inference": "single_pass",
            "segmentation_canvas_size": 320,
        },
        "segmentation": {
            "checkpoint": segmentation_output.name,
            "checkpoint_sha256": sha256_file(segmentation_output),
            "model_name": "BakeSmartLRASPP",
            "validation_mean_iou": mean_iou,
            "validation_pixel_accuracy": pixel_accuracy,
        },
        "door": {
            "checkpoint": door_output.name,
            "checkpoint_sha256": sha256_file(door_output),
            "model_name": "BakeSmartDoorDetectorV6",
            "validation_positive_scene_count": validation_positive_count,
            "validation_calibrated_f1": calibrated_f1,
            "validation_mean_best_iou": mean_best_iou,
            "score_threshold": threshold,
        },
        "limitations": [
            "The Door validation result is based on two positive scenes.",
            "Outlet detection is disabled because only three positive training scenes were available.",
            "Runtime segmentation uses one 320-pixel pass; reported v5 metrics came from offline tiled validation.",
            "No candidate is a measured or confirmed 3D obstacle.",
            "The locked test split remains untouched.",
        ],
    }
    manifest_path = output_dir / "bundle_manifest.json"
    temporary = manifest_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    # Preserve the detailed reports beside the compact runtime artifacts.
    shutil.copy2(segmentation_dir / "validation_report.json", output_dir / "segmentation_validation_report.json")
    shutil.copy2(door_dir / "validation_report.json", output_dir / "door_validation_report.json")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segmentation-dir", default=str(DEFAULT_SEGMENTATION_DIR))
    parser.add_argument("--door-dir", default=str(DEFAULT_DOOR_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        manifest = finalize(
            segmentation_dir=Path(args.segmentation_dir),
            door_dir=Path(args.door_dir),
            output_dir=Path(args.output_dir),
        )
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("BakeSmart v6 validation-only vision bundle is ready")
    print(f"Room mIoU:             {manifest['segmentation']['validation_mean_iou']:.4f}")
    print(f"Room pixel accuracy:   {manifest['segmentation']['validation_pixel_accuracy']:.4f}")
    print(f"Door calibrated F1:    {manifest['door']['validation_calibrated_f1']:.4f}")
    print(f"Door score threshold:  {manifest['door']['score_threshold']:.2f}")
    print("Outlet mode:            customer manual")
    print("Production approved:    NO")
    print("Locked test used:       NO")
    print(f"Bundle:                  {Path(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
