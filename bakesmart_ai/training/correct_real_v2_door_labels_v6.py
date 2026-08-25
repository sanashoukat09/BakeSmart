"""Apply the confirmed Door-to-Window correction and rebuild development splits.

Full-resolution review showed that ``real-venue-0038`` contains a window wall,
not a Door. Its class-2 pixels made one of only two Door validation scenes a
false target. This command backs up every changed metadata file, converts only
those development-mask pixels from Door (2) to Window (3), refreshes checksums,
and rebuilds the corrected and v5 development manifests. Locked-test files are
never opened and locked-test rows are preserved verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from training.annotation_workspace import PROJECT_DIR
from training.prepare_real_venue_v5_split import build_v5_split
from training.prepare_repaired_real_venue_dataset import prepare_repaired_dataset


SCENE_ID = "real-venue-0038"
DOOR_ID = 2
WINDOW_ID = 3
DEFAULT_REPAIRED_ROOT = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
)
DEFAULT_SOURCE_MANIFEST = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2"
    / "splits" / "split_manifest.json"
)


class DoorLabelCorrectionError(ValueError):
    """Raised when the correction cannot be applied safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _backup_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
        raise DoorLabelCorrectionError(f"missing or unreadable JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise DoorLabelCorrectionError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def correct_labels(labels: np.ndarray) -> tuple[np.ndarray, int]:
    """Convert only Door pixels to Window pixels and return the change count."""
    source = np.asarray(labels, dtype=np.uint8)
    corrected = source.copy()
    selected = corrected == DOOR_ID
    changed = int(selected.sum())
    corrected[selected] = WINDOW_ID
    return corrected, changed


def _save_mask(labels: np.ndarray, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    Image.fromarray(labels.astype(np.uint8)).save(temporary, format="PNG")
    temporary.replace(path)


def apply_correction(
    repaired_root: Path = DEFAULT_REPAIRED_ROOT,
    source_manifest: Path = DEFAULT_SOURCE_MANIFEST,
    *,
    project_dir: Path = PROJECT_DIR,
) -> dict[str, object]:
    repaired_root = repaired_root.resolve()
    source_manifest = source_manifest.resolve()
    mask_path = repaired_root / "masks" / f"{SCENE_ID}.png"
    record_path = repaired_root / "annotation_records" / f"{SCENE_ID}.json"
    audit_path = repaired_root / "diagnostics" / "rare_class_visual_audit.json"
    split_dir = repaired_root / "splits"
    required = (mask_path, record_path, audit_path, source_manifest)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise DoorLabelCorrectionError("required file is missing: " + ", ".join(missing))

    source = _load_json(source_manifest)
    source_rows = source.get("scenes")
    if not isinstance(source_rows, list):
        raise DoorLabelCorrectionError("source manifest has no scene rows")
    source_row = next(
        (
            row for row in source_rows
            if isinstance(row, dict) and row.get("scene_id") == SCENE_ID
        ),
        None,
    )
    if source_row is None or source_row.get("split") == "test":
        raise DoorLabelCorrectionError(
            f"{SCENE_ID} must exist in the unlocked development split"
        )

    with Image.open(mask_path) as opened:
        labels = np.asarray(opened.convert("L"), dtype=np.uint8)
    corrected, changed_pixels = correct_labels(labels)
    timestamp = _utc_now()

    paths_to_backup = [mask_path, record_path, audit_path]
    for name in ("split_manifest.json", "split_manifest.csv", "v5_split_manifest.json"):
        candidate = split_dir / name
        if candidate.is_file():
            paths_to_backup.append(candidate)
    backup_root = (
        repaired_root / "diagnostics" / "v6_door_label_backups" / _backup_stamp()
    )
    backup_root.mkdir(parents=True, exist_ok=False)
    for path in paths_to_backup:
        relative = path.relative_to(repaired_root)
        target = backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    try:
        if changed_pixels:
            _save_mask(corrected, mask_path)

        record = _load_json(record_path)
        record["mask_sha256"] = _sha256(mask_path)
        record["updated_at"] = timestamp
        record["review_notes"] = (
            "v6 full-resolution review: previous Door pixels were window structure; "
            "reclassified Door (2) to Window (3)."
        )
        _write_json(record_path, record)

        audit = _load_json(audit_path)
        scenes = audit.get("scenes")
        if not isinstance(scenes, dict):
            raise DoorLabelCorrectionError("rare-class audit has no scene decisions")
        scene = scenes.get(SCENE_ID)
        if not isinstance(scene, dict):
            scene = {}
            scenes[SCENE_ID] = scene
        scene.update(
            {
                "decision": "looks_correct",
                "notes": (
                    "v6 correction applied: false Door pixels reclassified as Window "
                    "after full-resolution review."
                ),
                "updated_at": timestamp,
            }
        )
        audit["test_split_used"] = False
        _write_json(audit_path, audit)

        corrected_manifest = prepare_repaired_dataset(
            source_manifest,
            repaired_root,
            project_dir=project_dir,
        )
        v5_path = split_dir / "v5_split_manifest.json"
        v5_manifest = build_v5_split(
            split_dir / "split_manifest.json",
            v5_path,
            project_dir=project_dir,
        )
    except Exception:
        for path in paths_to_backup:
            saved = backup_root / path.relative_to(repaired_root)
            if saved.is_file():
                shutil.copy2(saved, path)
        raise

    v5_rows = v5_manifest.get("scenes")
    validation_door_ids = sorted(
        str(row["scene_id"])
        for row in v5_rows
        if isinstance(row, dict)
        and row.get("split") == "validation"
        and DOOR_ID in row.get("class_ids_present", [])
    )
    report = {
        "schema_version": 6,
        "generated_at_utc": timestamp,
        "scene_id": SCENE_ID,
        "correction": {"from": "door", "from_id": 2, "to": "window", "to_id": 3},
        "pixels_changed": changed_pixels,
        "backup_directory": str(backup_root.relative_to(project_dir)),
        "corrected_manifest_counts": corrected_manifest["counts"],
        "v5_validation_door_scenes": validation_door_ids,
        "test_split_used": False,
    }
    report_path = repaired_root / "diagnostics" / "v6_door_label_correction.json"
    _write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repaired-root", type=Path, default=DEFAULT_REPAIRED_ROOT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    args = parser.parse_args()
    try:
        report = apply_correction(args.repaired_root, args.source_manifest)
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("BakeSmart v6 Door label correction is ready")
    print(f"Scene corrected:          {report['scene_id']}")
    print(f"Door pixels -> Window:    {report['pixels_changed']:,}")
    print(
        "Validation Door scenes: "
        + ", ".join(report["v5_validation_door_scenes"])
    )
    print("Locked test used:         NO")
    print(f"Backup:                   {report['backup_directory']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
