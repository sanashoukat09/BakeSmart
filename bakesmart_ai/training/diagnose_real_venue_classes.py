"""Diagnose rare semantic classes without opening the locked test images.

This Step-4 diagnostic uses only the locked training and validation memberships.
It measures class presence and pixel survival at raw, 256x256 and 512x512
letterboxed resolutions. If the local v1 checkpoint exists, it also runs that
checkpoint on the nine validation scenes at its native preprocessing size and
reports whether Door/Outlet are never predicted or merely predicted incorrectly.

The locked test split is never requested through ``samples_for_split`` and no
test image or mask file is opened.

Run from ``bakesmart_ai``::

    python -m training.diagnose_real_venue_classes
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
    import torch
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Step 4 diagnostic dependencies are missing. Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR, UNLABELLED_ID
from training.real_venue_segmentation import (
    BakeSmartVenueUNet,
    CLASS_NAMES,
    NUM_CLASSES,
    RealVenueSegmentationDataset,
    SegmentationConfusion,
    SplitSample,
    _validate_mask_values,
    letterbox_pair,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
)


DEFAULT_MANIFEST = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "raw"
    / "real_v2"
    / "splits"
    / "split_manifest.json"
)
DEFAULT_V1_CHECKPOINT = PROJECT_DIR / "models" / "venue_vision_real_v1" / "best_model.pt"
DEFAULT_OUTPUT_DIR = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2" / "diagnostics"
)
RARE_CLASS_NAMES = ("door", "outlet")
RESOLUTIONS = (256, 512)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def choose_device(requested: str) -> torch.device:
    requested = requested.strip().lower()
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but PyTorch cannot access a CUDA GPU")
    if requested not in {"cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    return torch.device(requested)


def _read_pair(sample: SplitSample) -> tuple[Image.Image, Image.Image]:
    with Image.open(sample.image_path) as source_image:
        image = ImageOps.exif_transpose(source_image).convert("RGB")
    with Image.open(sample.mask_path) as source_mask:
        mask = source_mask.convert("L")
    if image.size != mask.size:
        raise ValueError(
            f"image/mask dimensions differ for {sample.scene_id}: {image.size} vs {mask.size}"
        )
    _validate_mask_values(np.asarray(mask, dtype=np.uint8), sample.scene_id)
    return image, mask


def class_counts(mask: np.ndarray) -> dict[str, int]:
    return {
        name: int(np.count_nonzero(mask == class_id))
        for class_id, name in enumerate(CLASS_NAMES)
    }


def component_stats(mask: np.ndarray, class_id: int) -> dict[str, int]:
    """Return connected-component details on a resized mask for one class."""
    binary = (mask == class_id).astype(np.uint8)
    if not np.any(binary):
        return {"components": 0, "largest_component_pixels": 0}
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        binary,
        connectivity=8,
    )
    if count <= 1:
        return {"components": 0, "largest_component_pixels": 0}
    areas = stats[1:, cv2.CC_STAT_AREA]
    return {
        "components": int(count - 1),
        "largest_component_pixels": int(areas.max(initial=0)),
    }


def inspect_sample(sample: SplitSample) -> dict[str, object]:
    image, mask = _read_pair(sample)
    raw = np.asarray(mask, dtype=np.uint8)
    valid_raw = int(np.count_nonzero(raw != UNLABELLED_ID))
    row: dict[str, object] = {
        "scene_id": sample.scene_id,
        "split": sample.split,
        "width": int(mask.width),
        "height": int(mask.height),
        "valid_pixels_raw": valid_raw,
    }
    raw_counts = class_counts(raw)
    for name in CLASS_NAMES:
        count = raw_counts[name]
        row[f"{name}_raw_pixels"] = count
        row[f"{name}_raw_fraction"] = round(count / max(valid_raw, 1), 8)

    for size in RESOLUTIONS:
        _resized_image, resized_mask = letterbox_pair(image, mask, size)
        labels = np.asarray(resized_mask, dtype=np.uint8)
        valid = int(np.count_nonzero(labels != UNLABELLED_ID))
        counts = class_counts(labels)
        row[f"valid_pixels_{size}"] = valid
        for class_id, name in enumerate(CLASS_NAMES):
            count = counts[name]
            row[f"{name}_{size}_pixels"] = count
            row[f"{name}_{size}_fraction"] = round(count / max(valid, 1), 8)
            if name in RARE_CLASS_NAMES and size == 512:
                components = component_stats(labels, class_id)
                row[f"{name}_512_components"] = components["components"]
                row[f"{name}_512_largest_component_pixels"] = components[
                    "largest_component_pixels"
                ]
    return row


def summarize_rows(rows: list[dict[str, object]], split: str) -> dict[str, object]:
    selected = [row for row in rows if row["split"] == split]
    if not selected:
        raise ValueError(f"no rows available for split {split}")
    summary: dict[str, object] = {
        "scene_count": len(selected),
        "classes": {},
    }
    for name in CLASS_NAMES:
        per_scene_raw = [int(row[f"{name}_raw_pixels"]) for row in selected]
        per_scene_256 = [int(row[f"{name}_256_pixels"]) for row in selected]
        per_scene_512 = [int(row[f"{name}_512_pixels"]) for row in selected]
        present_raw = [value for value in per_scene_raw if value > 0]
        present_256 = [value for value in per_scene_256 if value > 0]
        present_512 = [value for value in per_scene_512 if value > 0]
        raw_total = sum(per_scene_raw)
        raw_valid_total = sum(int(row["valid_pixels_raw"]) for row in selected)
        summary["classes"][name] = {
            "scenes_present_raw": len(present_raw),
            "scene_presence_fraction": round(len(present_raw) / len(selected), 6),
            "raw_pixels_total": raw_total,
            "raw_fraction_of_labelled_pixels": round(raw_total / max(raw_valid_total, 1), 8),
            "raw_pixels_median_when_present": int(median(present_raw)) if present_raw else 0,
            "pixels_256_total": sum(per_scene_256),
            "pixels_256_median_when_present": int(median(present_256)) if present_256 else 0,
            "raw_present_but_lost_at_256": sum(
                1 for raw_value, resized in zip(per_scene_raw, per_scene_256)
                if raw_value > 0 and resized == 0
            ),
            "pixels_512_total": sum(per_scene_512),
            "pixels_512_median_when_present": int(median(present_512)) if present_512 else 0,
            "raw_present_but_lost_at_512": sum(
                1 for raw_value, resized in zip(per_scene_raw, per_scene_512)
                if raw_value > 0 and resized == 0
            ),
        }
        if name in RARE_CLASS_NAMES:
            summary["classes"][name]["components_512_total"] = sum(
                int(row[f"{name}_512_components"]) for row in selected
            )
            largest_values = [
                int(row[f"{name}_512_largest_component_pixels"])
                for row in selected
                if int(row[f"{name}_512_pixels"]) > 0
            ]
            summary["classes"][name]["largest_component_512_median_when_present"] = (
                int(median(largest_values)) if largest_values else 0
            )
    return summary


def _load_v1_model(
    checkpoint_path: Path,
    *,
    manifest_path: Path,
    device: torch.device,
) -> tuple[BakeSmartVenueUNet, dict[str, object], int]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(checkpoint, dict):
        raise ValueError("v1 checkpoint is not a dictionary")
    if checkpoint.get("model_name") != "BakeSmartVenueUNet":
        raise ValueError("v1 checkpoint has an unexpected model name")
    if list(checkpoint.get("class_names") or []) != list(CLASS_NAMES):
        raise ValueError("v1 checkpoint class names do not match the six-class schema")
    if checkpoint.get("pretrained") is not False:
        raise ValueError("v1 checkpoint provenance is inconsistent: pretrained must be false")
    if checkpoint.get("test_data_used") is not False:
        raise ValueError("refusing diagnostic checkpoint that records test_data_used=true")
    manifest_sha = sha256_file(manifest_path)
    if checkpoint.get("manifest_sha256") != manifest_sha:
        raise ValueError("v1 checkpoint was trained against a different split manifest")
    config = checkpoint.get("config") or {}
    if not isinstance(config, dict):
        raise ValueError("v1 checkpoint config is invalid")
    base_channels = int(config.get("base_channels", 16))
    image_size = int(config.get("image_size", 256))
    model = BakeSmartVenueUNet(base_channels=base_channels).to(device)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    return model, checkpoint, image_size


@torch.no_grad()
def diagnose_v1_predictions(
    validation_samples: list[SplitSample],
    *,
    checkpoint_path: Path,
    manifest_path: Path,
    device: torch.device,
) -> tuple[dict[str, object], dict[str, dict[str, int]]]:
    model, checkpoint, image_size = _load_v1_model(
        checkpoint_path,
        manifest_path=manifest_path,
        device=device,
    )
    dataset = RealVenueSegmentationDataset(
        validation_samples,
        image_size=image_size,
        augment=False,
    )
    confusion = SegmentationConfusion()
    predicted_totals = defaultdict(int)
    truth_totals = defaultdict(int)
    scene_details: dict[str, dict[str, int]] = {}

    for index in range(len(dataset)):
        image, mask, scene_id = dataset[index]
        logits = model(image.unsqueeze(0).to(device))
        prediction = torch.argmax(logits, dim=1).squeeze(0).cpu()
        confusion.update(mask.unsqueeze(0), prediction.unsqueeze(0))
        valid = mask != UNLABELLED_ID
        detail: dict[str, int] = {}
        for class_id, name in enumerate(CLASS_NAMES):
            truth_count = int(torch.count_nonzero((mask == class_id) & valid).item())
            predicted_count = int(
                torch.count_nonzero((prediction == class_id) & valid).item()
            )
            truth_totals[name] += truth_count
            predicted_totals[name] += predicted_count
            detail[f"{name}_v1_truth_pixels"] = truth_count
            detail[f"{name}_v1_predicted_pixels"] = predicted_count
        scene_details[scene_id] = detail

    metrics = confusion.metrics()
    class_behavior: dict[str, object] = {}
    for name in CLASS_NAMES:
        truth_count = int(truth_totals[name])
        predicted_count = int(predicted_totals[name])
        if truth_count == 0:
            interpretation = "class_absent_from_validation_ground_truth"
        elif predicted_count == 0:
            interpretation = "never_predicted"
        else:
            iou = metrics["per_class"][name]["iou"]
            interpretation = "predicted_but_no_overlap" if not iou else "predicted_with_overlap"
        class_behavior[name] = {
            "ground_truth_pixels": truth_count,
            "predicted_pixels": predicted_count,
            "prediction_to_truth_ratio": (
                None if truth_count == 0 else round(predicted_count / truth_count, 6)
            ),
            "iou": metrics["per_class"][name]["iou"],
            "precision": metrics["per_class"][name]["precision"],
            "recall": metrics["per_class"][name]["recall"],
            "interpretation": interpretation,
        }

    return (
        {
            "checkpoint": str(checkpoint_path.relative_to(PROJECT_DIR)),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "checkpoint_epoch": int(checkpoint.get("epoch", 0)),
            "native_image_size": image_size,
            "device": str(device),
            "validation_metrics": metrics,
            "class_behavior": class_behavior,
        },
        scene_details,
    )


def build_findings(
    split_summary: dict[str, object],
    model_summary: dict[str, object] | None,
) -> list[str]:
    findings: list[str] = []
    validation = split_summary["validation"]["classes"]
    for name in RARE_CLASS_NAMES:
        stats = validation[name]
        present = int(stats["scenes_present_raw"])
        if present == 0:
            findings.append(
                f"{name}: absent from all validation masks; validation IoU cannot test this class."
            )
            continue
        lost_256 = int(stats["raw_present_but_lost_at_256"])
        lost_512 = int(stats["raw_present_but_lost_at_512"])
        if lost_256 > 0:
            findings.append(
                f"{name}: present in {present} validation scenes, but disappears completely "
                f"after 256x256 preprocessing in {lost_256} scene(s)."
            )
        else:
            findings.append(
                f"{name}: survives 256x256 preprocessing in every validation scene where it is labelled."
            )
        if lost_512 > 0:
            findings.append(
                f"{name}: still disappears after 512x512 preprocessing in {lost_512} scene(s)."
            )
    if model_summary is not None:
        behavior = model_summary["class_behavior"]
        for name in RARE_CLASS_NAMES:
            findings.append(
                f"v1 {name}: {behavior[name]['interpretation']} "
                f"(truth={behavior[name]['ground_truth_pixels']}, "
                f"predicted={behavior[name]['predicted_pixels']}, "
                f"IoU={behavior[name]['iou']})."
            )
    return findings


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def diagnose(args: argparse.Namespace) -> dict[str, object]:
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    checkpoint_path = Path(args.v1_checkpoint).resolve()
    if not manifest_path.is_file():
        raise ValueError("locked Step-3 split manifest is missing")

    manifest = load_locked_split_manifest(manifest_path, project_dir=PROJECT_DIR)
    train_samples = samples_for_split(
        manifest,
        "train",
        project_dir=PROJECT_DIR,
        verify_hashes=True,
    )
    validation_samples = samples_for_split(
        manifest,
        "validation",
        project_dir=PROJECT_DIR,
        verify_hashes=True,
    )
    # IMPORTANT: no samples_for_split(..., "test") call exists in this diagnostic.

    print("BakeSmart Step 4 — Venue Class Diagnostic")
    print(f"Training scenes inspected:   {len(train_samples)}")
    print(f"Validation scenes inspected: {len(validation_samples)}")
    print("Locked test images opened:   0")
    print("Inspecting masks at raw, 256x256 and 512x512 resolutions...")

    rows = [inspect_sample(sample) for sample in train_samples + validation_samples]
    split_summary = {
        "train": summarize_rows(rows, "train"),
        "validation": summarize_rows(rows, "validation"),
    }

    model_summary: dict[str, object] | None = None
    if args.skip_v1:
        print("v1 prediction diagnostic:    skipped by --skip-v1")
    elif checkpoint_path.is_file():
        device = choose_device(args.device)
        print(f"v1 prediction diagnostic:    running on {device}")
        model_summary, scene_predictions = diagnose_v1_predictions(
            validation_samples,
            checkpoint_path=checkpoint_path,
            manifest_path=manifest_path,
            device=device,
        )
        for row in rows:
            if row["split"] == "validation":
                row.update(scene_predictions[str(row["scene_id"])])
    else:
        print(f"v1 prediction diagnostic:    checkpoint not found ({checkpoint_path})")

    findings = build_findings(split_summary, model_summary)
    report = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "purpose": "Step-4 class imbalance and rare-class failure diagnosis",
        "dataset": "real_v2",
        "split_manifest": str(manifest_path.relative_to(PROJECT_DIR)),
        "split_manifest_sha256": sha256_file(manifest_path),
        "train_scene_count": len(train_samples),
        "validation_scene_count": len(validation_samples),
        "locked_test_scene_count_from_manifest": int(manifest["counts"]["test"]),
        "test_image_files_opened": 0,
        "test_mask_files_opened": 0,
        "test_split_used": False,
        "resolutions_checked": list(RESOLUTIONS),
        "split_summary": split_summary,
        "v1_prediction_diagnostic": model_summary,
        "findings": findings,
        "production_ready": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "step4_class_diagnostic.json"
    csv_path = output_dir / "step4_class_diagnostic_scenes.csv"
    temporary = json_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(json_path)
    write_csv(csv_path, rows)

    print("\nClass presence and resizing survival")
    for split in ("train", "validation"):
        print(f"\n{split.title()}:")
        for name in CLASS_NAMES:
            stats = split_summary[split]["classes"][name]
            print(
                f"  {name:<10} scenes {stats['scenes_present_raw']:>2}/{split_summary[split]['scene_count']} | "
                f"raw {stats['raw_pixels_total']:>12,} px | "
                f"256 {stats['pixels_256_total']:>7,} px | "
                f"512 {stats['pixels_512_total']:>8,} px | "
                f"lost@256 {stats['raw_present_but_lost_at_256']}"
            )

    if model_summary is not None:
        print("\nv1 validation prediction behaviour")
        for name in CLASS_NAMES:
            behavior = model_summary["class_behavior"][name]
            iou = behavior["iou"]
            iou_text = "n/a" if iou is None else f"{float(iou):.4f}"
            print(
                f"  {name:<10} truth {behavior['ground_truth_pixels']:>7,} | "
                f"pred {behavior['predicted_pixels']:>7,} | "
                f"IoU {iou_text:<6} | {behavior['interpretation']}"
            )

    print("\nDiagnostic findings")
    for finding in findings:
        print(f"- {finding}")
    print(f"\nJSON report: {json_path.relative_to(PROJECT_DIR)}")
    print(f"CSV detail:  {csv_path.relative_to(PROJECT_DIR)}")
    print("Locked test set remains untouched.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--v1-checkpoint", default=str(DEFAULT_V1_CHECKPOINT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--skip-v1",
        action="store_true",
        help="Run dataset/mask diagnostics without loading the v1 checkpoint.",
    )
    return parser


def main() -> int:
    try:
        diagnose(build_parser().parse_args())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
