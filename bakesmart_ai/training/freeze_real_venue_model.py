"""Complete the rare-class gate and freeze the best validation model.

This command never loads the locked test split. It requires every current
train/validation Door-or-Outlet audit scene to be marked ``looks_correct``,
re-evaluates all available v1/v2/v3 checkpoints through one common validation
pipeline, then freezes the highest balanced validation score.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyTorch is required. Run: pip install -r requirements.txt") from exc

from training.annotation_workspace import PROJECT_DIR
from training.rare_class_audit_workspace import DEFAULT_AUDIT_STATE
from training.real_venue_model_evaluation import evaluate_samples, load_checkpoint_model
from training.real_venue_segmentation import (
    CLASS_NAMES,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
)
from training.train_real_venue_segmentation import DEFAULT_MANIFEST, choose_device
from training.train_real_venue_segmentation_v3 import balanced_validation_score


DEFAULT_CANDIDATES = (
    PROJECT_DIR / "models" / "venue_vision_real_v1" / "best_model.pt",
    PROJECT_DIR / "models" / "venue_vision_real_v2" / "best_model.pt",
    PROJECT_DIR / "models" / "venue_vision_real_v3" / "best_model.pt",
)
DEFAULT_SELECTED_DIR = PROJECT_DIR / "models" / "venue_vision_real_selected"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is missing or unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def validate_rare_class_audit(
    manifest: dict[str, object],
    audit_state: dict[str, object],
) -> dict[str, int]:
    if audit_state.get("test_split_used") is not False:
        raise ValueError("rare-class audit must record test_split_used=false")
    expected: set[str] = set()
    for row in manifest["scenes"]:
        if row.get("split") not in {"train", "validation"}:
            continue
        present = row.get("class_ids_present")
        if not isinstance(present, list):
            raise ValueError(
                "split manifest must record class_ids_present before audit finalization"
            )
        if 2 in present or 5 in present:
            expected.add(str(row["scene_id"]))
    if not expected:
        raise ValueError("no Door/Outlet train or validation scenes were found")
    decisions = audit_state.get("scenes")
    if not isinstance(decisions, dict):
        raise ValueError("rare-class audit contains no scene decisions")
    counts = {"total": len(expected), "looks_correct": 0, "pending": 0, "label_issue": 0, "unsure": 0}
    for scene_id in sorted(expected):
        row = decisions.get(scene_id)
        decision = str(row.get("decision") if isinstance(row, dict) else "pending")
        if decision not in {"looks_correct", "label_issue", "unsure"}:
            decision = "pending"
        counts[decision] += 1
    test_ids = {
        str(row["scene_id"])
        for row in manifest["scenes"]
        if row.get("split") == "test"
    }
    if test_ids.intersection(decisions):
        raise ValueError("rare-class audit contains a forbidden locked-test decision")
    unresolved = counts["pending"] + counts["label_issue"] + counts["unsure"]
    if unresolved:
        raise ValueError(
            "Door/Outlet audit is not complete: "
            f"pending={counts['pending']}, label_issue={counts['label_issue']}, "
            f"unsure={counts['unsure']}"
        )
    return counts


def choose_best_result(results: list[dict[str, object]]) -> dict[str, object]:
    if not results:
        raise ValueError("no valid v1/v2/v3 checkpoint is available")
    return max(
        results,
        key=lambda row: (
            float(row["balanced_validation_score"]),
            float(row["metrics"]["mean_iou"]),
            str(row["variant"]),
        ),
    )


def freeze(args: argparse.Namespace) -> dict[str, object]:
    manifest_path = Path(args.manifest).resolve()
    audit_path = Path(args.audit_state).resolve()
    selected_dir = Path(args.selected_dir).resolve()
    selection_path = selected_dir / "model_selection.json"
    locked_report = selected_dir / "locked_test_report.json"
    if locked_report.exists():
        raise ValueError("a locked-test report already exists; model selection is immutable")
    if selection_path.exists() and not args.force_refreeze:
        raise ValueError("model is already frozen; use --force-refreeze only before locked-test evaluation")

    manifest = load_locked_split_manifest(manifest_path, project_dir=PROJECT_DIR)
    manifest_sha = sha256_file(manifest_path)
    audit = load_json(audit_path, "rare-class audit state")
    audit_summary = validate_rare_class_audit(manifest, audit)
    validation_samples = samples_for_split(
        manifest, "validation", project_dir=PROJECT_DIR, verify_hashes=True
    )
    device = choose_device(args.device)
    results: list[dict[str, object]] = []
    for path_text in args.candidate:
        checkpoint_path = Path(path_text).resolve()
        if not checkpoint_path.is_file():
            continue
        model, checkpoint = load_checkpoint_model(
            checkpoint_path,
            device=device,
            expected_manifest_sha256=manifest_sha,
        )
        metrics, _per_scene = evaluate_samples(
            model,
            validation_samples,
            device=device,
            canvas_size=args.canvas_size,
            tile_size=args.tile_size,
            tile_stride=args.tile_stride,
        )
        variant = str(checkpoint.get("training_variant") or "baseline_v1")
        results.append(
            {
                "variant": variant,
                "checkpoint": str(checkpoint_path),
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "balanced_validation_score": round(
                    balanced_validation_score(metrics), 6
                ),
                "metrics": metrics,
                "base_channels": int(checkpoint["config"]["base_channels"]),
            }
        )
    winner = choose_best_result(results)
    selected_dir.mkdir(parents=True, exist_ok=True)
    frozen_checkpoint = selected_dir / "best_model.pt"
    temporary_checkpoint = frozen_checkpoint.with_suffix(".pt.part")
    shutil.copy2(Path(str(winner["checkpoint"])), temporary_checkpoint)
    temporary_checkpoint.replace(frozen_checkpoint)
    frozen_sha = sha256_file(frozen_checkpoint)
    model_version = f"venue-vision-real-six-class-{frozen_sha[:12]}"
    report = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "status": "frozen_pending_locked_test",
        "model_version": model_version,
        "model_name": "BakeSmartVenueUNet",
        "class_names": list(CLASS_NAMES),
        "pretrained": False,
        "random_initialization": True,
        "production_approved": False,
        "api_runtime_candidate": False,
        "test_split_used": False,
        "split_manifest": str(manifest_path.relative_to(PROJECT_DIR)),
        "split_manifest_sha256": manifest_sha,
        "audit_state": str(audit_path.relative_to(PROJECT_DIR)),
        "audit_state_sha256": sha256_file(audit_path),
        "audit_summary": audit_summary,
        "selection_policy": "common 512px tiled validation; 0.80 mIoU + 0.10 Door IoU + 0.10 Outlet IoU",
        "inference": {
            "canvas_size": args.canvas_size,
            "tile_size": args.tile_size,
            "tile_stride": args.tile_stride,
            "maximum_reported_confidence": 0.49,
        },
        "candidates": results,
        "selected_variant": winner["variant"],
        "selected_validation_metrics": winner["metrics"],
        "selected_balanced_validation_score": winner["balanced_validation_score"],
        "base_channels": winner["base_channels"],
        "checkpoint": str(frozen_checkpoint.relative_to(PROJECT_DIR)),
        "checkpoint_sha256": frozen_sha,
    }
    temporary_report = selection_path.with_suffix(".json.part")
    temporary_report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary_report.replace(selection_path)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--audit-state", default=str(DEFAULT_AUDIT_STATE))
    parser.add_argument("--selected-dir", default=str(DEFAULT_SELECTED_DIR))
    parser.add_argument(
        "--candidate",
        action="append",
        default=None,
        help="Checkpoint path; repeat for multiple candidates (defaults to v1/v2/v3).",
    )
    parser.add_argument("--canvas-size", type=int, default=512)
    parser.add_argument("--tile-size", type=int, default=256)
    parser.add_argument("--tile-stride", type=int, default=192)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--force-refreeze", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.candidate is None:
        args.candidate = [str(path) for path in DEFAULT_CANDIDATES]
    try:
        report = freeze(args)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("PASS: Door/Outlet audit is complete and the best validation model is frozen")
    print(f"Selected: {report['selected_variant']}")
    print(f"Validation score: {report['selected_balanced_validation_score']:.4f}")
    print("Locked test remains untouched. Run Step 5 explicitly when ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
