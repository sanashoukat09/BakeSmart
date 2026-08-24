"""Run BakeSmart's one-time final evaluation on the locked real-photo test set."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyTorch is required. Run: pip install -r requirements.txt") from exc

from training.annotation_workspace import PROJECT_DIR
from training.freeze_real_venue_model import DEFAULT_SELECTED_DIR, load_json
from training.real_venue_model_evaluation import (
    evaluate_samples,
    load_checkpoint_model,
    locked_test_samples,
)
from training.real_venue_segmentation import (
    load_locked_split_manifest,
    sha256_file,
)
from training.train_real_venue_segmentation import DEFAULT_MANIFEST, choose_device


ACKNOWLEDGEMENT = "I_UNDERSTAND_THIS_OPENS_THE_LOCKED_TEST_ONCE"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def evaluate_locked_test(args: argparse.Namespace) -> dict[str, object]:
    if args.acknowledge_locked_test != ACKNOWLEDGEMENT:
        raise ValueError(
            "locked-test acknowledgement is required: "
            f"--acknowledge-locked-test {ACKNOWLEDGEMENT}"
        )
    selected_dir = Path(args.selected_dir).resolve()
    selection_path = selected_dir / "model_selection.json"
    report_path = selected_dir / "locked_test_report.json"
    if report_path.exists():
        raise ValueError(
            "locked-test report already exists; evaluation will not be repeated"
        )
    selection = load_json(selection_path, "frozen model selection")
    if selection.get("status") != "frozen_pending_locked_test":
        raise ValueError("model selection is not frozen and pending locked test")
    if selection.get("test_split_used") is not False:
        raise ValueError("selection metadata says the test split was already used")

    manifest_path = Path(args.manifest).resolve()
    manifest_sha = sha256_file(manifest_path)
    if manifest_sha != selection.get("split_manifest_sha256"):
        raise ValueError("locked split changed after model freezing")
    manifest = load_locked_split_manifest(manifest_path, project_dir=PROJECT_DIR)
    checkpoint_path = PROJECT_DIR / str(selection["checkpoint"])
    if sha256_file(checkpoint_path) != selection.get("checkpoint_sha256"):
        raise ValueError("frozen checkpoint checksum does not match selection record")

    device = choose_device(args.device)
    model, _checkpoint = load_checkpoint_model(
        checkpoint_path,
        device=device,
        expected_manifest_sha256=manifest_sha,
    )
    samples = locked_test_samples(
        manifest, project_dir=PROJECT_DIR, verify_hashes=True
    )
    inference = selection["inference"]
    metrics, per_scene = evaluate_samples(
        model,
        samples,
        device=device,
        canvas_size=int(inference["canvas_size"]),
        tile_size=int(inference["tile_size"]),
        tile_stride=int(inference["tile_stride"]),
    )
    report = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "status": "final_locked_test_complete",
        "one_time_evaluation": True,
        "model_version": selection["model_version"],
        "selected_variant": selection["selected_variant"],
        "class_names": selection["class_names"],
        "pretrained": False,
        "random_initialization": True,
        "production_approved": False,
        "test_split_used": True,
        "test_scene_count": len(samples),
        "split_manifest_sha256": manifest_sha,
        "checkpoint_sha256": selection["checkpoint_sha256"],
        "inference": inference,
        "metrics": metrics,
        "per_scene": per_scene,
        "limitations": [
            "The locked test contains a small number of reviewed real venues.",
            "Predictions remain unconfirmed visual candidates and do not provide physical scale.",
            "Production approval requires application integration and physical-device testing.",
        ],
    }
    selected_dir.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(report_path)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--selected-dir", default=str(DEFAULT_SELECTED_DIR))
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--acknowledge-locked-test")
    return parser


def main() -> int:
    try:
        report = evaluate_locked_test(build_parser().parse_args())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("PASS: final locked real-photo test evaluation completed once")
    print(f"Scenes:         {report['test_scene_count']}")
    print(f"Mean IoU:       {report['metrics']['mean_iou']:.4f}")
    print(f"Pixel accuracy: {report['metrics']['pixel_accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
