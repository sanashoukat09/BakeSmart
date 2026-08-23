"""Independent review state for completed BakeSmart venue annotations.

Reviewers inspect already-completed masks. This module never edits semantic
mask pixels. It only records an independent decision: approved,
needs_correction, or rejected.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from training.annotation_workspace import ANNOTATOR_ID_PATTERN, PROJECT_DIR
from training.semantic_annotation_workspace import SemanticAnnotationWorkspace


REVIEW_DECISIONS = {"approved", "needs_correction", "rejected"}
REVIEWABLE_STATUS = "annotation_complete_pending_review"


@dataclass(frozen=True)
class ReviewSummary:
    total: int
    pending: int
    approved: int
    needs_correction: int
    rejected: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "pending": self.pending,
            "approved": self.approved,
            "needs_correction": self.needs_correction,
            "rejected": self.rejected,
        }


class VenueReviewWorkspace:
    def __init__(
        self,
        project_dir: Path = PROJECT_DIR,
        workspace: SemanticAnnotationWorkspace | None = None,
    ) -> None:
        self.workspace = workspace or SemanticAnnotationWorkspace(project_dir)

    def list_scenes(self, dataset_key: str = "real_v2") -> list[dict[str, object]]:
        scenes: list[dict[str, object]] = []
        for descriptor in self.workspace.list_scenes(dataset_key):
            scene_id = str(descriptor["scene_id"])
            record = self.workspace.load_record(dataset_key, scene_id) or {}
            review_status = str(record.get("review_status") or "pending_independent_review")
            scenes.append(
                {
                    **descriptor,
                    "annotator_id": record.get("annotator_id"),
                    "reviewer_id": record.get("reviewer_id"),
                    "review_status": review_status,
                    "review_notes": record.get("review_notes") or "",
                    "review_completed_at": record.get("review_completed_at"),
                    "training_status": record.get("training_status") or "not_for_training",
                    "reviewable": (
                        descriptor.get("status") == REVIEWABLE_STATUS
                        and descriptor.get("has_mask") is True
                    ),
                }
            )
        return scenes

    def summary(self, dataset_key: str = "real_v2") -> ReviewSummary:
        scenes = self.list_scenes(dataset_key)
        counts = {decision: 0 for decision in REVIEW_DECISIONS}
        pending = 0
        for scene in scenes:
            status = str(scene.get("review_status") or "")
            if status in counts:
                counts[status] += 1
            else:
                pending += 1
        return ReviewSummary(
            total=len(scenes),
            pending=pending,
            approved=counts["approved"],
            needs_correction=counts["needs_correction"],
            rejected=counts["rejected"],
        )

    def normalized_image_png(self, dataset_key: str, scene_id: str) -> bytes:
        path = self.workspace.image_path(dataset_key, scene_id)
        with Image.open(path) as source:
            normalized = ImageOps.exif_transpose(source).convert("RGB")
            output = io.BytesIO()
            normalized.save(output, format="PNG")
        return output.getvalue()

    def mask_overlay_png(self, dataset_key: str, scene_id: str) -> bytes:
        return self.workspace.overlay_png(dataset_key, scene_id)

    def submit_review(
        self,
        *,
        dataset_key: str,
        scene_id: str,
        reviewer_id: str,
        decision: str,
        notes: str | None = None,
    ) -> dict[str, object]:
        reviewer = self._normalize_reviewer_id(reviewer_id)
        normalized_decision = (decision or "").strip().lower()
        if normalized_decision not in REVIEW_DECISIONS:
            raise ValueError(
                "review decision must be approved, needs_correction, or rejected"
            )
        normalized_notes = (notes or "").strip()
        if normalized_decision in {"needs_correction", "rejected"} and not normalized_notes:
            raise ValueError("review notes are required for correction or rejection")

        record = self.workspace.load_record(dataset_key, scene_id)
        if record is None:
            raise ValueError("annotation record is missing")
        if record.get("status") != REVIEWABLE_STATUS:
            raise ValueError("scene is not a completed annotation ready for review")
        if not self.workspace.mask_path(dataset_key, scene_id).is_file():
            raise ValueError("semantic mask is missing")

        annotator = str(record.get("annotator_id") or "").strip()
        if not annotator:
            raise ValueError("annotation record has no annotator ID")
        if reviewer.casefold() == annotator.casefold():
            raise ValueError("reviewer must be different from the annotator")

        labels = self.workspace._read_saved_mask(  # noqa: SLF001
            self.workspace.mask_path(dataset_key, scene_id),
            self.workspace._image_size(dataset_key, scene_id),  # noqa: SLF001
        )
        stats = self.workspace.validate_labels(labels)
        if not stats["complete"]:
            raise ValueError("semantic mask is incomplete and cannot be reviewed")

        updated = dict(record)
        updated["reviewer_id"] = reviewer
        updated["review_status"] = normalized_decision
        updated["review_notes"] = normalized_notes
        updated["review_completed_at"] = self.workspace._utc_now()  # noqa: SLF001
        if normalized_decision == "approved":
            updated["training_status"] = "approved_pending_split"
        elif normalized_decision == "needs_correction":
            updated["training_status"] = "not_for_training"
        else:
            updated["training_status"] = "rejected"
        self.workspace._write_record(dataset_key, scene_id, updated)  # noqa: SLF001

        return {
            "scene_id": scene_id,
            "review_status": normalized_decision,
            "reviewer_id": reviewer,
            "review_notes": normalized_notes,
            "review_completed_at": updated["review_completed_at"],
            "training_status": updated["training_status"],
        }

    @staticmethod
    def _normalize_reviewer_id(value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("reviewer ID is required")
        if not ANNOTATOR_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                "reviewer ID must be 1-80 characters using letters, numbers, spaces, . _ @ + or -"
            )
        return normalized
