"""Create the locked train/validation/test split for approved real venue masks.

Step 3 runs only after independent mask review is complete. It uses only scenes
with ``review_status=approved`` and ``training_status=approved_pending_split``
(or an existing Step-3 split status), creates an exact 70/15/15 split, balances
semantic class presence where possible, writes CSV/JSON manifests, and records
split membership in each annotation sidecar.

The first successful run locks the split manifest. Re-running verifies and
reuses that manifest. Replacing a locked split requires BOTH
``--force-resplit`` and ``--acknowledge-test-lock-reset``.

Run from ``bakesmart_ai``::

    python -m training.split_real_venue_dataset
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from training.semantic_annotation_workspace import (
    SEMANTIC_LABEL_CLASSES,
    SEMANTIC_LABEL_IDS,
    SemanticAnnotationWorkspace,
)


DEFAULT_SEED = 260823
SPLIT_ORDER = ("train", "validation", "test")
SPLIT_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
SPLIT_TRAINING_STATUS = {
    "train": "approved_for_training",
    "validation": "approved_for_validation",
    "test": "approved_for_locked_test",
}
ALLOWED_APPROVED_STATUSES = {
    "approved_pending_split",
    *SPLIT_TRAINING_STATUS.values(),
}


class SplitError(ValueError):
    """Raised when the reviewed real dataset is not safe to split."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _allocate_counts(total: int) -> dict[str, int]:
    if total < 3:
        raise SplitError("at least 3 approved scenes are required for a 70/15/15 split")
    raw = {name: total * SPLIT_RATIOS[name] for name in SPLIT_ORDER}
    counts = {name: int(math.floor(raw[name])) for name in SPLIT_ORDER}
    remaining = total - sum(counts.values())
    ranked = sorted(
        SPLIT_ORDER,
        key=lambda name: (raw[name] - counts[name], -SPLIT_ORDER.index(name)),
        reverse=True,
    )
    for name in ranked[:remaining]:
        counts[name] += 1
    if any(counts[name] == 0 for name in SPLIT_ORDER):
        raise SplitError("approved dataset is too small to keep all three splits non-empty")
    return counts


def _stable_tie(seed: int, scene_id: str, split: str = "") -> int:
    payload = f"{seed}:{scene_id}:{split}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _balanced_assignments(
    scenes: list[dict[str, object]],
    targets: dict[str, int],
    *,
    seed: int,
) -> dict[str, str]:
    """Greedily distribute rare semantic classes while respecting exact sizes."""
    total = len(scenes)
    class_totals = Counter()
    for scene in scenes:
        class_totals.update(int(value) for value in scene["class_ids_present"])

    desired = {
        split: {
            class_id: class_totals[class_id] * targets[split] / total
            for class_id in SEMANTIC_LABEL_IDS
        }
        for split in SPLIT_ORDER
    }
    current = {
        split: Counter({class_id: 0 for class_id in SEMANTIC_LABEL_IDS})
        for split in SPLIT_ORDER
    }
    assigned_count = Counter({split: 0 for split in SPLIT_ORDER})

    def rare_score(scene: dict[str, object]) -> float:
        score = 0.0
        for class_id in scene["class_ids_present"]:
            count = class_totals[int(class_id)]
            score += 1.0 / max(count, 1)
        return score

    ordered = list(scenes)
    random.Random(seed).shuffle(ordered)
    ordered.sort(
        key=lambda scene: (
            -rare_score(scene),
            -len(scene["class_ids_present"]),
            _stable_tie(seed, str(scene["scene_id"])),
        )
    )

    assignments: dict[str, str] = {}
    for scene in ordered:
        eligible = [
            split
            for split in SPLIT_ORDER
            if assigned_count[split] < targets[split]
        ]
        if not eligible:
            raise SplitError("internal split error: no capacity remains")

        def candidate_score(split: str) -> tuple[float, float, int]:
            # Normalized class deficit rewards placing a scene where its classes
            # are currently most under-represented. Fill ratio keeps each split
            # progressing proportionally toward its fixed capacity.
            deficit = 0.0
            for class_id in scene["class_ids_present"]:
                wanted = desired[split][int(class_id)]
                have = current[split][int(class_id)]
                deficit += max(wanted - have, 0.0) / max(wanted, 1.0)
            fill_ratio = assigned_count[split] / max(targets[split], 1)
            return (
                deficit - 0.35 * fill_ratio,
                -fill_ratio,
                -_stable_tie(seed, str(scene["scene_id"]), split),
            )

        chosen = max(eligible, key=candidate_score)
        assignments[str(scene["scene_id"])] = chosen
        assigned_count[chosen] += 1
        current[chosen].update(int(value) for value in scene["class_ids_present"])

    if dict(assigned_count) != targets:
        raise SplitError(
            f"internal split error: expected {targets}, produced {dict(assigned_count)}"
        )
    return assignments


class RealVenueDatasetSplitter:
    def __init__(self, workspace: SemanticAnnotationWorkspace | None = None) -> None:
        self.workspace = workspace or SemanticAnnotationWorkspace()

    def run(
        self,
        *,
        dataset_key: str = "real_v2",
        seed: int = DEFAULT_SEED,
        force_resplit: bool = False,
        acknowledge_test_lock_reset: bool = False,
    ) -> dict[str, object]:
        if dataset_key != "real_v2":
            raise SplitError("Step 3 currently supports only real_v2")
        if force_resplit and not acknowledge_test_lock_reset:
            raise SplitError(
                "--force-resplit requires --acknowledge-test-lock-reset because the test set is locked"
            )

        dataset = self.workspace._dataset(dataset_key)  # noqa: SLF001
        split_dir = dataset.masks_dir.parent / "splits"
        json_path = split_dir / "split_manifest.json"
        csv_path = split_dir / "split_manifest.csv"

        reviewed = self._collect_reviewed_scenes(dataset_key)
        approved = [scene for scene in reviewed if scene["review_status"] == "approved"]
        unresolved = [
            scene
            for scene in reviewed
            if scene["review_status"] not in {"approved", "rejected"}
        ]
        if unresolved:
            ids = ", ".join(str(scene["scene_id"]) for scene in unresolved[:8])
            suffix = "..." if len(unresolved) > 8 else ""
            raise SplitError(
                f"Step 2 is not complete: {len(unresolved)} scene(s) still need review: {ids}{suffix}"
            )
        if not approved:
            raise SplitError("no independently approved real venue masks were found")

        self._validate_approved_scenes(dataset_key, approved)
        approved_ids = sorted(str(scene["scene_id"]) for scene in approved)

        if json_path.is_file() and not force_resplit:
            manifest = self._load_locked_manifest(json_path)
            self._verify_locked_manifest(
                dataset_key=dataset_key,
                manifest=manifest,
                approved_ids=approved_ids,
            )
            print("Existing locked split verified; no scenes were reassigned.")
            return manifest

        targets = _allocate_counts(len(approved))
        assignments = _balanced_assignments(approved, targets, seed=seed)
        generated_at = _utc_now()
        rows = self._manifest_rows(dataset_key, approved, assignments)
        summary = self._summary(rows, targets)

        manifest: dict[str, object] = {
            "schema_version": 1,
            "dataset": dataset_key,
            "created_at_utc": generated_at,
            "seed": seed,
            "ratios": SPLIT_RATIOS,
            "counts": targets,
            "approved_scene_count": len(approved),
            "rejected_scene_count": sum(
                scene["review_status"] == "rejected" for scene in reviewed
            ),
            "semantic_class_ids": list(SEMANTIC_LABEL_IDS),
            "semantic_classes": [label.key for label in SEMANTIC_LABEL_CLASSES],
            "test_set_locked": True,
            "policy": (
                "Only independently approved real_v2 scenes are eligible. "
                "Assignments use fixed-seed class-presence balancing. The test split "
                "must remain unseen during model development and tuning."
            ),
            "summary": summary,
            "scenes": rows,
        }

        split_dir.mkdir(parents=True, exist_ok=True)
        self._write_csv(csv_path, rows)
        self._write_json(json_path, manifest)
        self._update_records(
            dataset_key=dataset_key,
            rows=rows,
            seed=seed,
            manifest_path=json_path,
            assigned_at=generated_at,
        )
        return manifest

    def _collect_reviewed_scenes(self, dataset_key: str) -> list[dict[str, object]]:
        scenes: list[dict[str, object]] = []
        for descriptor in self.workspace.list_scenes(dataset_key):
            scene_id = str(descriptor["scene_id"])
            record = self.workspace.load_record(dataset_key, scene_id)
            if record is None:
                raise SplitError(f"annotation record is missing: {scene_id}")
            scenes.append(
                {
                    "scene_id": scene_id,
                    "review_status": str(record.get("review_status") or "pending_independent_review"),
                    "training_status": str(record.get("training_status") or "not_for_training"),
                    "record": record,
                }
            )
        return scenes

    def _validate_approved_scenes(
        self,
        dataset_key: str,
        approved: list[dict[str, object]],
    ) -> None:
        seen_image_hashes: dict[str, str] = {}
        for scene in approved:
            scene_id = str(scene["scene_id"])
            record = scene["record"]
            training_status = str(scene["training_status"])
            if training_status not in ALLOWED_APPROVED_STATUSES:
                raise SplitError(
                    f"approved scene {scene_id} has unexpected training_status={training_status}"
                )
            if not record.get("reviewer_id"):
                raise SplitError(f"approved scene has no reviewer_id: {scene_id}")
            if not record.get("review_completed_at"):
                raise SplitError(f"approved scene has no review_completed_at: {scene_id}")

            mask_path = self.workspace.mask_path(dataset_key, scene_id)
            walkway_path = self.workspace.walkway_path(dataset_key, scene_id)
            if not mask_path.is_file():
                raise SplitError(f"approved scene is missing semantic mask: {scene_id}")
            if not walkway_path.is_file():
                raise SplitError(f"approved scene is missing walkway mask: {scene_id}")

            labels = self.workspace._read_saved_mask(  # noqa: SLF001
                mask_path,
                self.workspace._image_size(dataset_key, scene_id),  # noqa: SLF001
            )
            stats = self.workspace.validate_labels(labels)
            if not stats["complete"]:
                raise SplitError(f"approved semantic mask is incomplete: {scene_id}")
            scene["class_ids_present"] = [
                int(class_id)
                for class_id in SEMANTIC_LABEL_IDS
                if bool(np.any(labels == class_id))
            ]

            image_path = self.workspace.image_path(dataset_key, scene_id)
            image_hash = self.workspace._sha256_file(image_path)  # noqa: SLF001
            duplicate = seen_image_hashes.get(image_hash)
            if duplicate is not None:
                raise SplitError(
                    f"duplicate approved image bytes detected: {duplicate} and {scene_id}"
                )
            seen_image_hashes[image_hash] = scene_id

    def _manifest_rows(
        self,
        dataset_key: str,
        approved: list[dict[str, object]],
        assignments: dict[str, str],
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for scene in sorted(approved, key=lambda item: str(item["scene_id"])):
            scene_id = str(scene["scene_id"])
            record = scene["record"]
            image_path = self.workspace.image_path(dataset_key, scene_id)
            mask_path = self.workspace.mask_path(dataset_key, scene_id)
            walkway_path = self.workspace.walkway_path(dataset_key, scene_id)
            rows.append(
                {
                    "scene_id": scene_id,
                    "split": assignments[scene_id],
                    "image_path": self.workspace._relative(image_path),  # noqa: SLF001
                    "mask_path": self.workspace._relative(mask_path),  # noqa: SLF001
                    "walkway_mask_path": self.workspace._relative(walkway_path),  # noqa: SLF001
                    "image_sha256": self.workspace._sha256_file(image_path),  # noqa: SLF001
                    "mask_sha256": self.workspace._sha256_file(mask_path),  # noqa: SLF001
                    "walkway_sha256": self.workspace._sha256_file(walkway_path),  # noqa: SLF001
                    "annotator_id": record.get("annotator_id") or "",
                    "reviewer_id": record.get("reviewer_id") or "",
                    "review_completed_at": record.get("review_completed_at") or "",
                    "class_ids_present": list(scene["class_ids_present"]),
                }
            )
        return rows

    @staticmethod
    def _summary(
        rows: list[dict[str, object]],
        targets: dict[str, int],
    ) -> dict[str, object]:
        class_presence: dict[str, dict[str, int]] = {
            split: {str(class_id): 0 for class_id in SEMANTIC_LABEL_IDS}
            for split in SPLIT_ORDER
        }
        for row in rows:
            split = str(row["split"])
            for class_id in row["class_ids_present"]:
                class_presence[split][str(class_id)] += 1
        return {
            "counts": targets,
            "class_presence_by_split": class_presence,
            "overlap_check": "passed",
            "test_set_locked": True,
        }

    def _update_records(
        self,
        *,
        dataset_key: str,
        rows: list[dict[str, object]],
        seed: int,
        manifest_path: Path,
        assigned_at: str,
    ) -> None:
        for row in rows:
            scene_id = str(row["scene_id"])
            record = self.workspace.load_record(dataset_key, scene_id)
            if record is None:
                raise SplitError(f"annotation record disappeared during split: {scene_id}")
            split = str(row["split"])
            updated = dict(record)
            updated.update(
                {
                    "dataset_split": split,
                    "split_seed": seed,
                    "split_assigned_at": assigned_at,
                    "split_manifest_path": self.workspace._relative(manifest_path),  # noqa: SLF001
                    "training_status": SPLIT_TRAINING_STATUS[split],
                }
            )
            self.workspace._write_record(dataset_key, scene_id, updated)  # noqa: SLF001

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        fields = (
            "scene_id",
            "split",
            "image_path",
            "mask_path",
            "walkway_mask_path",
            "image_sha256",
            "mask_sha256",
            "walkway_sha256",
            "annotator_id",
            "reviewer_id",
            "review_completed_at",
            "class_ids_present",
        )
        temporary = path.with_suffix(".csv.part")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                export = dict(row)
                export["class_ids_present"] = "|".join(
                    str(value) for value in row["class_ids_present"]
                )
                writer.writerow(export)
        temporary.replace(path)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        temporary = path.with_suffix(".json.part")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _load_locked_manifest(path: Path) -> dict[str, object]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SplitError("locked split manifest is unreadable") from exc
        if not isinstance(payload, dict) or payload.get("test_set_locked") is not True:
            raise SplitError("existing split manifest is invalid or not locked")
        return payload

    def _verify_locked_manifest(
        self,
        *,
        dataset_key: str,
        manifest: dict[str, object],
        approved_ids: list[str],
    ) -> None:
        rows = manifest.get("scenes")
        if not isinstance(rows, list):
            raise SplitError("locked split manifest has no valid scene list")
        manifest_ids = sorted(str(row.get("scene_id")) for row in rows if isinstance(row, dict))
        if manifest_ids != approved_ids:
            raise SplitError(
                "approved scene set changed after the split was locked; do not silently reshuffle. "
                "Review the change first, then deliberately use --force-resplit "
                "--acknowledge-test-lock-reset if a new split is truly required."
            )

        seen: set[str] = set()
        counts = Counter()
        for row in rows:
            if not isinstance(row, dict):
                raise SplitError("locked split manifest contains an invalid row")
            scene_id = str(row.get("scene_id") or "")
            split = str(row.get("split") or "")
            if scene_id in seen:
                raise SplitError(f"locked split contains duplicate scene: {scene_id}")
            if split not in SPLIT_ORDER:
                raise SplitError(f"locked split contains invalid membership for {scene_id}")
            seen.add(scene_id)
            counts[split] += 1

            image_path = self.workspace.image_path(dataset_key, scene_id)
            mask_path = self.workspace.mask_path(dataset_key, scene_id)
            walkway_path = self.workspace.walkway_path(dataset_key, scene_id)
            expected = {
                "image_sha256": self.workspace._sha256_file(image_path),  # noqa: SLF001
                "mask_sha256": self.workspace._sha256_file(mask_path),  # noqa: SLF001
                "walkway_sha256": self.workspace._sha256_file(walkway_path),  # noqa: SLF001
            }
            for key, actual in expected.items():
                if row.get(key) != actual:
                    raise SplitError(
                        f"{scene_id} changed after split locking ({key}); review before training"
                    )

        manifest_counts = manifest.get("counts")
        if not isinstance(manifest_counts, dict):
            raise SplitError("locked split manifest has no count summary")
        expected_counts = {name: int(manifest_counts[name]) for name in SPLIT_ORDER}
        if dict(counts) != expected_counts:
            raise SplitError(
                f"locked split count mismatch: manifest={expected_counts}, rows={dict(counts)}"
            )


def print_summary(manifest: dict[str, object]) -> None:
    counts = manifest["counts"]
    print("\nBakeSmart Real Venue Dataset Split")
    print(f"Approved scenes: {manifest['approved_scene_count']}")
    print(f"Training:        {counts['train']}")
    print(f"Validation:      {counts['validation']}")
    print(f"Test (locked):   {counts['test']}")
    print(f"Seed:            {manifest['seed']}")
    print("Overlap:         none")
    print("Test lock:       ON")
    print("\nDo not use validation/test masks as training examples.")
    print("Do not inspect test performance while tuning the Step-4 model.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="real_v2")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--force-resplit", action="store_true")
    parser.add_argument("--acknowledge-test-lock-reset", action="store_true")
    args = parser.parse_args()
    try:
        manifest = RealVenueDatasetSplitter().run(
            dataset_key=args.dataset,
            seed=args.seed,
            force_resplit=args.force_resplit,
            acknowledge_test_lock_reset=args.acknowledge_test_lock_reset,
        )
    except (OSError, SplitError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print_summary(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
