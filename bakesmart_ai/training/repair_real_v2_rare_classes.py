"""Reproduce the curated Door/Outlet repair for the 60-scene real_v2 dataset.

The source dataset is never edited. The command writes a new dataset directory,
removes the obsolete split lock, regenerates walkway masks, updates checksums,
and resets every scene to pending independent review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from training.annotation_workspace import PROJECT_DIR


DEFAULT_SOURCE = PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2"
DEFAULT_OUTPUT = PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"

# Ranks are ordered by descending 8-connected component area. These selections
# were made from full-resolution image/mask overlays, not model predictions.
DOOR_KEEP_RANKS: dict[str, set[int]] = {
    "real-venue-0001": {0},
    "real-venue-0004": {0, 1},
    "real-venue-0009": {0, 1, 2, 3},
    "real-venue-0014": {0},
    "real-venue-0016": {0},
    "real-venue-0017": {0, 1},
    "real-venue-0022": {0},
    "real-venue-0023": {0, 1, 2, 3, 4},
    "real-venue-0026": {0},
    "real-venue-0030": {0},
    "real-venue-0035": {0},
    "real-venue-0036": {0},
    "real-venue-0038": {0},
    "real-venue-0042": {0},
    "real-venue-0048": {0},
    "real-venue-0052": {0, 1, 2},
    "real-venue-0054": {0, 1, 2, 3},
    "real-venue-0063": {0},
    "real-venue-0065": {0},
}

OUTLET_KEEP_RANKS: dict[str, set[int]] = {
    "real-venue-0022": {0, 1, 2},
    "real-venue-0023": {0},
    "real-venue-0030": {0},
    "real-venue-0034": {0, 1, 2},
    "real-venue-0047": {0, 1, 2},
    "real-venue-0048": {3},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _components(
    labels: np.ndarray,
    class_id: int,
) -> tuple[np.ndarray, list[tuple[int, int, tuple[slice, slice]]]]:
    count, component_labels, stats, _centroids = cv2.connectedComponentsWithStats(
        (labels == class_id).astype(np.uint8), connectivity=8
    )
    result: list[tuple[int, int, tuple[slice, slice]]] = []
    for component_id in range(1, count):
        x = int(stats[component_id, cv2.CC_STAT_LEFT])
        y = int(stats[component_id, cv2.CC_STAT_TOP])
        width = int(stats[component_id, cv2.CC_STAT_WIDTH])
        height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        result.append(
            (component_id, area, (slice(y, y + height), slice(x, x + width)))
        )
    result.sort(key=lambda item: item[1], reverse=True)
    return component_labels, result


def _component_count(labels: np.ndarray, class_id: int) -> int:
    count, _labels = cv2.connectedComponents(
        (labels == class_id).astype(np.uint8), connectivity=8
    )
    return int(count - 1)


def _surrounding_class(
    labels: np.ndarray,
    slices: tuple[slice, slice],
    padding: int = 12,
) -> int:
    y_slice, x_slice = slices
    region = labels[
        max(0, y_slice.start - padding) : min(labels.shape[0], y_slice.stop + padding),
        max(0, x_slice.start - padding) : min(labels.shape[1], x_slice.stop + padding),
    ]
    candidates = region[np.isin(region, np.asarray([0, 1, 3, 4], dtype=np.uint8))]
    if not candidates.size:
        return 0
    return int(np.argmax(np.bincount(candidates, minlength=6)))


def _outlet_core(local_component: np.ndarray) -> np.ndarray:
    area = int(local_component.sum())
    if not area:
        return local_component
    target = min(area, max(150, round(area * 0.05)))
    distances = cv2.distanceTransform(
        local_component.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE
    )
    positive = distances[local_component]
    if positive.size <= target:
        return local_component
    threshold = np.partition(positive, positive.size - target)[positive.size - target]
    core = local_component & (distances >= threshold)
    if int(core.sum()) > max(target * 2, target + 100):
        coordinates = np.argwhere(core)
        center = (np.asarray(local_component.shape, dtype=np.float64) - 1.0) / 2.0
        order = np.argsort(np.sum((coordinates - center) ** 2, axis=1))
        selected = coordinates[order[:target]]
        core = np.zeros_like(local_component)
        core[selected[:, 0], selected[:, 1]] = True
    return core


def repair_mask(scene_id: str, labels: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    """Return the curated rare-class repair and an auditable change summary."""

    source = np.asarray(labels, dtype=np.uint8)
    repaired = source.copy()
    door_labels, door_components = _components(source, 2)
    outlet_labels, outlet_components = _components(source, 5)

    for rank, (component_id, _area, slices) in enumerate(door_components):
        if rank in DOOR_KEEP_RANKS.get(scene_id, set()):
            continue
        local = door_labels[slices] == component_id
        repaired[slices][local] = _surrounding_class(source, slices)

    for rank, (component_id, _area, slices) in enumerate(outlet_components):
        local = outlet_labels[slices] == component_id
        replacement = _surrounding_class(source, slices)
        if rank not in OUTLET_KEEP_RANKS.get(scene_id, set()):
            repaired[slices][local] = replacement
            continue
        core = _outlet_core(local)
        repaired[slices][local & ~core] = replacement
        repaired[slices][core] = 5

    changed = source != repaired
    if np.any(changed & ~np.isin(source, np.asarray([2, 5], dtype=np.uint8))):
        raise RuntimeError(f"repair changed a non-rare source pixel: {scene_id}")
    return repaired, {
        "scene_id": scene_id,
        "changed_pixels": int(changed.sum()),
        "before": {
            "door_components": _component_count(source, 2),
            "outlet_components": _component_count(source, 5),
        },
        "after": {
            "door_components": _component_count(repaired, 2),
            "outlet_components": _component_count(repaired, 5),
        },
    }


def _walkway(labels: np.ndarray) -> np.ndarray:
    clearance = min(24, max(1, round(min(labels.shape) * 0.015)))
    interior = cv2.erode(
        (labels == 1).astype(np.uint8),
        np.ones((3, 3), dtype=np.uint8),
        iterations=clearance,
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    count, components, stats, _centroids = cv2.connectedComponentsWithStats(
        interior, connectivity=4
    )
    minimum = max(9, round(labels.size * 0.0015))
    keep = np.zeros(count, dtype=bool)
    if count > 1:
        keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= minimum
    return keep[components].astype(np.uint8)


def _save_mask(labels: np.ndarray, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    Image.fromarray(labels.astype(np.uint8), mode="L").save(temporary, format="PNG")
    temporary.replace(path)


def _reset_record(
    source: Path,
    target: Path,
    mask: Path,
    walkway: Path,
    timestamp: str,
) -> None:
    record = json.loads(source.read_text(encoding="utf-8"))
    record.update(
        {
            "mask_sha256": _sha256(mask),
            "walkway_mask_sha256": _sha256(walkway),
            "updated_at": timestamp,
            "status": "annotation_complete_pending_review",
            "review_status": "pending_independent_review",
            "review_notes": "Door/outlet masks repaired; independent confirmation required.",
            "reviewer_id": None,
            "review_completed_at": None,
            "training_status": "not_for_training",
            "finalization_status": "pending_independent_review",
            "finalization_checked_at": None,
        }
    )
    for key in ("dataset_split", "split_assigned_at", "split_manifest_path", "split_seed"):
        record.pop(key, None)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_repaired_dataset(source: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    mask_paths = sorted((source / "masks").glob("*.png"))
    if len(mask_paths) != 60:
        raise ValueError(f"expected 60 real_v2 masks, found {len(mask_paths)}")

    shutil.copytree(source / "images", output / "images")
    shutil.copytree(source / "annotation_records", output / "annotation_records")
    (output / "masks").mkdir()
    (output / "walkway_masks").mkdir()
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    scenes: list[dict[str, object]] = []

    for index, source_mask in enumerate(mask_paths, 1):
        scene_id = source_mask.stem
        with Image.open(source_mask) as opened:
            labels = np.asarray(opened.convert("L"), dtype=np.uint8)
        repaired, details = repair_mask(scene_id, labels)
        mask_path = output / "masks" / source_mask.name
        walkway_path = output / "walkway_masks" / source_mask.name
        _save_mask(repaired, mask_path)
        _save_mask(_walkway(repaired), walkway_path)
        _reset_record(
            source / "annotation_records" / f"{scene_id}.json",
            output / "annotation_records" / f"{scene_id}.json",
            mask_path,
            walkway_path,
            timestamp,
        )
        scenes.append(details)
        print(f"[{index:02d}/60] {scene_id}: {details['changed_pixels']:,} pixels")

    report: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": timestamp,
        "classes_changed": {"2": "door", "5": "outlet"},
        "old_split_removed": True,
        "independent_confirmation_required": True,
        "summary": {
            "scenes": len(scenes),
            "scenes_changed": sum(bool(row["changed_pixels"]) for row in scenes),
            "pixels_changed": sum(int(row["changed_pixels"]) for row in scenes),
            "door_components_before": sum(int(row["before"]["door_components"]) for row in scenes),
            "door_components_after": sum(int(row["after"]["door_components"]) for row in scenes),
            "outlet_components_before": sum(int(row["before"]["outlet_components"]) for row in scenes),
            "outlet_components_after": sum(int(row["after"]["outlet_components"]) for row in scenes),
        },
        "scenes": scenes,
    }
    (output / "rare_class_repair_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="required confirmation; the source remains read-only",
    )
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit(
            "Dry safety stop: add --apply to create the separate repaired dataset."
        )
    report = build_repaired_dataset(args.source, args.output)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
