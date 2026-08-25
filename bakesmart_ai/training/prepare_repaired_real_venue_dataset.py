"""Lock corrected train/validation labels while preserving the original test split.

This command never opens a test image or mask. It reuses the nine original
locked-test manifest rows verbatim and rebuilds metadata only for corrected
training and validation scenes in ``real_v2_repaired``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from training.annotation_workspace import PROJECT_DIR
from training.semantic_annotation_workspace import SEMANTIC_LABEL_IDS
from training.split_real_venue_dataset import SPLIT_TRAINING_STATUS


DEFAULT_SOURCE_MANIFEST = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2"
    / "splits" / "split_manifest.json"
)
DEFAULT_REPAIRED_ROOT = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
)


class RepairedDatasetError(ValueError):
    """Raised when corrected data is not safe to use for training."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepairedDatasetError(f"JSON file is missing or unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise RepairedDatasetError(f"JSON root must be an object: {path}")
    return payload


def _relative(path: Path, project_dir: Path) -> str:
    try:
        return path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError as exc:
        raise RepairedDatasetError(f"path is outside the project: {path}") from exc


def _read_labels(path: Path, expected_size: tuple[int, int]) -> np.ndarray:
    with Image.open(path) as opened:
        if opened.size != expected_size:
            raise RepairedDatasetError(
                f"mask size mismatch: {path.name} is {opened.size}, expected {expected_size}"
            )
        labels = np.asarray(opened.convert("L"), dtype=np.uint8)
    invalid = sorted(set(np.unique(labels).tolist()) - set(SEMANTIC_LABEL_IDS))
    if invalid:
        raise RepairedDatasetError(f"invalid semantic IDs in {path.name}: {invalid}")
    return labels


def _validate_audit(
    audit: dict[str, object],
    *,
    allowed_scene_ids: set[str],
    rare_scene_ids: set[str],
) -> None:
    if audit.get("dataset") != "real_v2_repaired":
        raise RepairedDatasetError("audit must identify dataset real_v2_repaired")
    if audit.get("test_split_used") is not False:
        raise RepairedDatasetError("audit must confirm test_split_used=false")
    scenes = audit.get("scenes")
    if not isinstance(scenes, dict):
        raise RepairedDatasetError("audit has no scene decisions")
    audited_ids = set(scenes)
    unexpected = sorted(audited_ids - allowed_scene_ids)
    if unexpected:
        raise RepairedDatasetError(
            "audit contains locked-test or unknown scenes: " + ", ".join(unexpected)
        )
    missing = sorted(rare_scene_ids - audited_ids)
    if missing:
        raise RepairedDatasetError(
            "rare-class audit is incomplete: " + ", ".join(missing)
        )
    unresolved = sorted(
        scene_id for scene_id in rare_scene_ids
        if not isinstance(scenes.get(scene_id), dict)
        or scenes[scene_id].get("decision") != "looks_correct"
    )
    if unresolved:
        raise RepairedDatasetError(
            "corrected labels still need approval: " + ", ".join(unresolved)
        )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = (
        "scene_id", "split", "image_path", "mask_path", "walkway_mask_path",
        "image_sha256", "mask_sha256", "walkway_sha256", "annotator_id",
        "reviewer_id", "review_completed_at", "class_ids_present",
    )
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            export = {key: row.get(key, "") for key in fields}
            export["class_ids_present"] = "|".join(
                str(value) for value in row.get("class_ids_present", [])
            )
            writer.writerow(export)
    temporary.replace(path)


def prepare_repaired_dataset(
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
    repaired_root: Path = DEFAULT_REPAIRED_ROOT,
    *,
    project_dir: Path = PROJECT_DIR,
) -> dict[str, object]:
    source_manifest_path = source_manifest_path.resolve()
    repaired_root = repaired_root.resolve()
    source = _load_json(source_manifest_path)
    if source.get("dataset") != "real_v2" or source.get("test_set_locked") is not True:
        raise RepairedDatasetError("source must be the original locked real_v2 manifest")
    source_rows = source.get("scenes")
    if not isinstance(source_rows, list) or not source_rows:
        raise RepairedDatasetError("source split has no scenes")

    rows: list[dict[str, object]] = []
    rare_scene_ids: set[str] = set()
    train_validation_ids: set[str] = set()
    image_hashes: dict[str, str] = {}
    counts: Counter[str] = Counter()

    for source_row in source_rows:
        if not isinstance(source_row, dict):
            raise RepairedDatasetError("source split contains an invalid row")
        scene_id = str(source_row.get("scene_id") or "")
        split = str(source_row.get("split") or "")
        if not scene_id or split not in {"train", "validation", "test"}:
            raise RepairedDatasetError("source split contains invalid membership")
        counts[split] += 1
        if split == "test":
            # Safety boundary: copy metadata only. Do not stat, hash, or open test files.
            rows.append(dict(source_row))
            continue

        train_validation_ids.add(scene_id)
        image_path = repaired_root / "images" / f"{scene_id}.jpg"
        mask_path = repaired_root / "masks" / f"{scene_id}.png"
        walkway_path = repaired_root / "walkway_masks" / f"{scene_id}.png"
        record_path = repaired_root / "annotation_records" / f"{scene_id}.json"
        for kind, path in (
            ("image", image_path), ("mask", mask_path),
            ("walkway mask", walkway_path), ("annotation record", record_path),
        ):
            if not path.is_file():
                raise RepairedDatasetError(f"{kind} is missing for {scene_id}: {path}")

        with Image.open(image_path) as opened:
            image_size = opened.size
        labels = _read_labels(mask_path, image_size)
        walkway = _read_labels(walkway_path, image_size)
        invalid_walkway = sorted(set(np.unique(walkway).tolist()) - {0, 1})
        if invalid_walkway:
            raise RepairedDatasetError(
                f"invalid walkway IDs for {scene_id}: {invalid_walkway}"
            )
        record = _load_json(record_path)
        mask_sha = _sha256(mask_path)
        walkway_sha = _sha256(walkway_path)
        if record.get("mask_sha256") != mask_sha:
            raise RepairedDatasetError(f"record mask checksum mismatch: {scene_id}")
        if record.get("walkway_mask_sha256") != walkway_sha:
            raise RepairedDatasetError(f"record walkway checksum mismatch: {scene_id}")
        image_sha = _sha256(image_path)
        duplicate = image_hashes.get(image_sha)
        if duplicate:
            raise RepairedDatasetError(
                f"duplicate repaired image bytes: {duplicate} and {scene_id}"
            )
        image_hashes[image_sha] = scene_id
        class_ids = [
            int(class_id) for class_id in SEMANTIC_LABEL_IDS
            if bool(np.any(labels == class_id))
        ]
        if 2 in class_ids or 5 in class_ids:
            rare_scene_ids.add(scene_id)
        rows.append(
            {
                "scene_id": scene_id,
                "split": split,
                "image_path": _relative(image_path, project_dir),
                "mask_path": _relative(mask_path, project_dir),
                "walkway_mask_path": _relative(walkway_path, project_dir),
                "image_sha256": image_sha,
                "mask_sha256": mask_sha,
                "walkway_sha256": walkway_sha,
                "annotator_id": record.get("annotator_id") or "",
                "reviewer_id": record.get("reviewer_id") or "",
                "review_completed_at": record.get("review_completed_at") or "",
                "class_ids_present": class_ids,
            }
        )

    expected_counts = {key: int(source["counts"][key]) for key in ("train", "validation", "test")}
    if dict(counts) != expected_counts:
        raise RepairedDatasetError(
            f"source split count mismatch: rows={dict(counts)}, summary={expected_counts}"
        )
    audit_path = repaired_root / "diagnostics" / "rare_class_visual_audit.json"
    _validate_audit(
        _load_json(audit_path),
        allowed_scene_ids=train_validation_ids,
        rare_scene_ids=rare_scene_ids,
    )

    generated_at = _utc_now()
    class_presence = {
        split: {str(class_id): 0 for class_id in SEMANTIC_LABEL_IDS}
        for split in ("train", "validation", "test")
    }
    for row in rows:
        for class_id in row.get("class_ids_present", []):
            class_presence[str(row["split"])][str(class_id)] += 1
    output_path = repaired_root / "splits" / "split_manifest.json"
    manifest: dict[str, object] = {
        "schema_version": 2,
        "dataset": "real_v2_repaired",
        "created_at_utc": generated_at,
        "source_split_manifest": _relative(source_manifest_path, project_dir),
        "source_split_manifest_sha256": _sha256(source_manifest_path),
        "counts": expected_counts,
        "approved_scene_count": sum(expected_counts.values()),
        "semantic_class_ids": list(SEMANTIC_LABEL_IDS),
        "semantic_classes": source.get("semantic_classes"),
        "test_set_locked": True,
        "test_membership_preserved": True,
        "test_rows_reused_verbatim": True,
        "test_split_used": False,
        "policy": (
            "Corrected labels are used only for the original train/validation membership. "
            "Original locked-test rows are copied verbatim and test files are not opened."
        ),
        "summary": {
            "counts": expected_counts,
            "class_presence_by_split": class_presence,
            "overlap_check": "passed",
            "test_set_locked": True,
        },
        "scenes": rows,
    }
    _write_json(output_path, manifest)
    _write_csv(output_path.with_suffix(".csv"), rows)

    for row in rows:
        if row["split"] == "test":
            continue
        scene_id = str(row["scene_id"])
        record_path = repaired_root / "annotation_records" / f"{scene_id}.json"
        record = _load_json(record_path)
        record.update(
            {
                "dataset": "real_v2_repaired",
                "dataset_split": row["split"],
                "split_assigned_at": generated_at,
                "split_manifest_path": _relative(output_path, project_dir),
                "training_status": SPLIT_TRAINING_STATUS[str(row["split"])],
            }
        )
        _write_json(record_path, record)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--repaired-root", type=Path, default=DEFAULT_REPAIRED_ROOT)
    args = parser.parse_args()
    try:
        manifest = prepare_repaired_dataset(args.source_manifest, args.repaired_root)
    except (OSError, RepairedDatasetError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    counts = manifest["counts"]
    print("BakeSmart corrected dataset is ready")
    print(f"Training scenes:    {counts['train']}")
    print(f"Validation scenes:  {counts['validation']}")
    print(f"Locked test scenes: {counts['test']} (membership unchanged; files unopened)")
    print("Audit issues:       0")
    print("Locked test used:   NO")
    print(f"Manifest:           {DEFAULT_REPAIRED_ROOT / 'splits' / 'split_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
