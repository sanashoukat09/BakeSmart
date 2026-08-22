"""Audit and standardize completed BakeSmart real-venue annotations.

This is Step 1 after manual annotation. It does NOT approve data for training.
It checks every real venue image/mask pair, migrates legacy class-6 Walkway
pixels back to class-1 Floor, creates a separate binary Walkway mask, verifies
there are no unlabelled/invalid pixels, checks completion records, and writes a
JSON audit report.

Before any legacy mask or annotation record is changed, the original file is
copied into a timestamped backup directory under the ignored real_v2 raw data.

Run from ``bakesmart_ai``::

    python -m training.finalize_real_venue_annotations

Preview without changing files::

    python -m training.finalize_real_venue_annotations --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from training.annotation_workspace import UNLABELLED_ID
from training.semantic_annotation_workspace import (
    SEMANTIC_LABEL_IDS,
    SemanticAnnotationWorkspace,
)
from training.walkway_generator import derive_walkway_candidate


LEGACY_WALKWAY_ID = 6
EXPECTED_STATUS = "annotation_complete_pending_review"
VALID_RAW_IDS = set(SEMANTIC_LABEL_IDS) | {LEGACY_WALKWAY_ID, UNLABELLED_ID}


@dataclass
class SceneAudit:
    scene_id: str
    image_path: str
    mask_path: str | None = None
    record_path: str | None = None
    image_size: list[int] | None = None
    mask_size: list[int] | None = None
    mask_mode: str | None = None
    original_ids: list[int] = field(default_factory=list)
    semantic_ids_after_migration: list[int] = field(default_factory=list)
    legacy_walkway_pixels: int = 0
    unlabelled_pixels: int = 0
    walkway_pixels: int = 0
    migrated_legacy_walkway: bool = False
    generated_walkway_mask: bool = False
    backup_paths: list[str] = field(default_factory=list)
    annotation_status: str | None = None
    ready_for_independent_review: bool = False
    issues: list[str] = field(default_factory=list)


class RealVenueAnnotationFinalizer:
    """Safely standardize real_v2 masks into the six-class v2 schema."""

    def __init__(self, workspace: SemanticAnnotationWorkspace | None = None) -> None:
        self.workspace = workspace or SemanticAnnotationWorkspace()

    def run(
        self,
        *,
        dataset_key: str = "real_v2",
        dry_run: bool = False,
    ) -> dict[str, object]:
        if dataset_key != "real_v2":
            raise ValueError("Step 1 finalization currently supports only real_v2")

        dataset = self.workspace._dataset(dataset_key)  # noqa: SLF001
        image_paths = self.workspace._image_paths(dataset)  # noqa: SLF001
        run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_root = dataset.masks_dir.parent / "backups" / "annotation_finalization" / run_stamp

        audits: list[SceneAudit] = []
        for index, image_path in enumerate(image_paths, start=1):
            scene_id = image_path.stem
            print(f"[{index}/{len(image_paths)}] {scene_id}", flush=True)
            audit = self._audit_scene(
                dataset_key=dataset_key,
                scene_id=scene_id,
                image_path=image_path,
                backup_root=backup_root,
                dry_run=dry_run,
            )
            audits.append(audit)
            if audit.ready_for_independent_review:
                print("    READY FOR REVIEW", flush=True)
            else:
                print("    NEEDS ATTENTION: " + "; ".join(audit.issues), flush=True)

        summary = self._summary(audits)
        report: dict[str, object] = {
            "schema_version": 1,
            "step": "real_venue_annotation_finalization",
            "dataset": dataset_key,
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "dry_run": dry_run,
            "semantic_schema": {
                "class_ids": list(SEMANTIC_LABEL_IDS),
                "classes": ["wall", "floor", "door", "window", "furniture", "outlet"],
                "unlabelled_id": UNLABELLED_ID,
                "legacy_walkway_id": LEGACY_WALKWAY_ID,
            },
            "walkway_schema": {
                "storage": "separate_binary_png",
                "values": {"0": "not_walkway", "1": "walkway_candidate"},
                "training_target": False,
                "metric_safety_clearance": False,
            },
            "training_status": "not_for_training",
            "next_gate": "independent_human_review",
            "summary": summary,
            "scenes": [asdict(audit) for audit in audits],
        }

        if not dry_run:
            report_dir = dataset.records_dir / "finalization_runs"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"finalize-{run_stamp}.json"
            temporary = report_path.with_suffix(".json.part")
            temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(report_path)
            report["report_path"] = self.workspace._relative(report_path)  # noqa: SLF001
            if backup_root.exists():
                report["backup_root"] = self.workspace._relative(backup_root)  # noqa: SLF001
        return report

    def _audit_scene(
        self,
        *,
        dataset_key: str,
        scene_id: str,
        image_path: Path,
        backup_root: Path,
        dry_run: bool,
    ) -> SceneAudit:
        mask_path = self.workspace.mask_path(dataset_key, scene_id)
        record_path = self.workspace.record_path(dataset_key, scene_id)
        audit = SceneAudit(
            scene_id=scene_id,
            image_path=self.workspace._relative(image_path),  # noqa: SLF001
            mask_path=self.workspace._relative(mask_path),  # noqa: SLF001
            record_path=self.workspace._relative(record_path),  # noqa: SLF001
        )

        try:
            with Image.open(image_path) as source:
                image_size = ImageOps.exif_transpose(source).size
        except (UnidentifiedImageError, OSError) as exc:
            audit.issues.append(f"image unreadable: {exc}")
            return audit
        audit.image_size = [int(image_size[0]), int(image_size[1])]

        if not mask_path.is_file():
            audit.issues.append("missing semantic mask")
            return audit

        try:
            with Image.open(mask_path) as mask_source:
                audit.mask_mode = mask_source.mode
                audit.mask_size = [int(mask_source.size[0]), int(mask_source.size[1])]
                if mask_source.mode != "L":
                    audit.issues.append(f"mask must be single-channel L mode, found {mask_source.mode}")
                    return audit
                raw_labels = np.asarray(mask_source, dtype=np.uint8).copy()
        except (UnidentifiedImageError, OSError) as exc:
            audit.issues.append(f"mask unreadable: {exc}")
            return audit

        if tuple(audit.mask_size) != tuple(audit.image_size):
            audit.issues.append(
                f"image/mask dimensions differ: image={audit.image_size}, mask={audit.mask_size}"
            )
            return audit

        original_ids = sorted(int(value) for value in np.unique(raw_labels))
        audit.original_ids = original_ids
        invalid_ids = set(original_ids) - VALID_RAW_IDS
        if invalid_ids:
            audit.issues.append(f"invalid mask IDs: {sorted(invalid_ids)}")
            return audit

        audit.legacy_walkway_pixels = int(np.count_nonzero(raw_labels == LEGACY_WALKWAY_ID))
        semantic_labels = raw_labels.copy()
        semantic_labels[semantic_labels == LEGACY_WALKWAY_ID] = 1
        audit.semantic_ids_after_migration = sorted(
            int(value) for value in np.unique(semantic_labels)
        )
        audit.unlabelled_pixels = int(np.count_nonzero(semantic_labels == UNLABELLED_ID))

        record = self.workspace.load_record(dataset_key, scene_id)
        if record is None:
            audit.issues.append("missing annotation record")
        else:
            audit.annotation_status = str(record.get("status") or "")
            if audit.annotation_status != EXPECTED_STATUS:
                audit.issues.append(
                    f"annotation status is {audit.annotation_status or 'missing'}, expected {EXPECTED_STATUS}"
                )
            if not record.get("annotator_id"):
                audit.issues.append("annotation record has no annotator_id")

        if audit.unlabelled_pixels:
            audit.issues.append(f"{audit.unlabelled_pixels} unlabelled pixel(s) remain")

        if not dry_run:
            backup_needed = audit.legacy_walkway_pixels > 0
            if backup_needed:
                audit.backup_paths.extend(
                    self._backup_legacy_files(
                        scene_id=scene_id,
                        mask_path=mask_path,
                        record_path=record_path,
                        backup_root=backup_root,
                    )
                )
                self._atomic_save_mask(mask_path, semantic_labels)
                audit.migrated_legacy_walkway = True

            walkway = derive_walkway_candidate(semantic_labels)
            self.workspace._save_walkway_mask(  # noqa: SLF001
                dataset_key,
                scene_id,
                walkway.walkway_mask,
            )
            audit.generated_walkway_mask = True
            audit.walkway_pixels = walkway.walkway_pixels

            if record is not None:
                self._update_record(
                    dataset_key=dataset_key,
                    scene_id=scene_id,
                    record=record,
                    migrated=audit.migrated_legacy_walkway,
                    run_stamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                )
        else:
            walkway = derive_walkway_candidate(semantic_labels)
            audit.walkway_pixels = walkway.walkway_pixels
            audit.migrated_legacy_walkway = audit.legacy_walkway_pixels > 0
            audit.generated_walkway_mask = True

        audit.ready_for_independent_review = not audit.issues
        return audit

    def _backup_legacy_files(
        self,
        *,
        scene_id: str,
        mask_path: Path,
        record_path: Path,
        backup_root: Path,
    ) -> list[str]:
        backup_root.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        mask_backup = backup_root / f"{scene_id}.legacy-mask.png"
        shutil.copy2(mask_path, mask_backup)
        paths.append(self.workspace._relative(mask_backup))  # noqa: SLF001
        if record_path.is_file():
            record_backup = backup_root / f"{scene_id}.legacy-record.json"
            shutil.copy2(record_path, record_backup)
            paths.append(self.workspace._relative(record_backup))  # noqa: SLF001
        return paths

    @staticmethod
    def _atomic_save_mask(path: Path, labels: np.ndarray) -> None:
        temporary = path.with_suffix(".png.part")
        Image.fromarray(np.asarray(labels, dtype=np.uint8), mode="L").save(
            temporary,
            format="PNG",
        )
        temporary.replace(path)

    def _update_record(
        self,
        *,
        dataset_key: str,
        scene_id: str,
        record: dict[str, object],
        migrated: bool,
        run_stamp: str,
    ) -> None:
        mask_path = self.workspace.mask_path(dataset_key, scene_id)
        walkway_path = self.workspace.walkway_path(dataset_key, scene_id)
        updated = dict(record)
        updated.update(
            {
                "semantic_schema_version": 2,
                "semantic_class_ids": list(SEMANTIC_LABEL_IDS),
                "mask_sha256": self.workspace._sha256_file(mask_path),  # noqa: SLF001
                "walkway_storage": "separate_binary_mask",
                "walkway_mask_path": self.workspace._relative(walkway_path),  # noqa: SLF001
                "walkway_mask_sha256": self.workspace._sha256_file(walkway_path),  # noqa: SLF001
                "finalization_checked_at": run_stamp,
                "finalization_status": "ready_for_independent_review",
                "training_status": "not_for_training",
            }
        )
        if migrated:
            updated["legacy_walkway_migrated_at"] = run_stamp
            updated["legacy_walkway_migration"] = "class_6_to_floor_class_1"
        self.workspace._write_record(dataset_key, scene_id, updated)  # noqa: SLF001

    @staticmethod
    def _summary(audits: list[SceneAudit]) -> dict[str, object]:
        return {
            "images_found": len(audits),
            "semantic_masks_found": sum("missing semantic mask" not in audit.issues for audit in audits),
            "valid_six_class_masks": sum(
                not any(
                    issue.startswith(("missing semantic mask", "mask unreadable", "mask must be", "image/mask dimensions differ", "invalid mask IDs",))
                    for issue in audit.issues
                )
                and audit.unlabelled_pixels == 0
                for audit in audits
            ),
            "missing_masks": sum("missing semantic mask" in audit.issues for audit in audits),
            "dimension_mismatches": sum(
                any(issue.startswith("image/mask dimensions differ") for issue in audit.issues)
                for audit in audits
            ),
            "invalid_masks": sum(
                any(issue.startswith(("mask unreadable", "mask must be", "invalid mask IDs")) for issue in audit.issues)
                for audit in audits
            ),
            "masks_with_unlabelled_pixels": sum(audit.unlabelled_pixels > 0 for audit in audits),
            "legacy_class6_masks": sum(audit.legacy_walkway_pixels > 0 for audit in audits),
            "legacy_class6_masks_migrated_or_planned": sum(audit.migrated_legacy_walkway for audit in audits),
            "walkway_masks_generated_or_planned": sum(audit.generated_walkway_mask for audit in audits),
            "missing_annotation_records": sum("missing annotation record" in audit.issues for audit in audits),
            "wrong_completion_status": sum(
                any(issue.startswith("annotation status is") for issue in audit.issues)
                for audit in audits
            ),
            "ready_for_independent_review": sum(audit.ready_for_independent_review for audit in audits),
            "needs_attention": sum(not audit.ready_for_independent_review for audit in audits),
            "all_ready_for_independent_review": bool(audits) and all(
                audit.ready_for_independent_review for audit in audits
            ),
        }


def print_summary(report: dict[str, object]) -> None:
    summary = report["summary"]
    print("\nBakeSmart Real Venue Dataset Finalization")
    print(f"Images found:                     {summary['images_found']}")
    print(f"Semantic masks found:             {summary['semantic_masks_found']}")
    print(f"Valid six-class masks:            {summary['valid_six_class_masks']}")
    print(f"Missing masks:                    {summary['missing_masks']}")
    print(f"Masks with unlabelled pixels:     {summary['masks_with_unlabelled_pixels']}")
    print(f"Legacy class-6 masks:             {summary['legacy_class6_masks']}")
    print(f"Legacy masks migrated/planned:    {summary['legacy_class6_masks_migrated_or_planned']}")
    print(f"Walkway masks generated/planned:  {summary['walkway_masks_generated_or_planned']}")
    print(f"Ready for independent review:     {summary['ready_for_independent_review']}")
    print(f"Needs attention:                  {summary['needs_attention']}")
    if report.get("report_path"):
        print(f"Report: {report['report_path']}")
    if report.get("backup_root"):
        print(f"Backups: {report['backup_root']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="real_v2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        report = RealVenueAnnotationFinalizer().run(
            dataset_key=args.dataset,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print_summary(report)
    return 0 if report["summary"]["all_ready_for_independent_review"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
