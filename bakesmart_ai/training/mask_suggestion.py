"""Machine-assisted draft masks for BakeSmart's local venue labeller.

Suggestions come only from BakeSmart's existing synthetic-bootstrap venue model.
They are never considered reviewed or training-approved annotations. The source
image and generated mask stay in the local ignored venue-vision workspace.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from training.annotation_workspace import AnnotationWorkspace
from training.venue_vision_data import VENUE_LABELS, extract_pixel_features
from training.venue_vision_runtime import VenueVisionRuntime


class MaskSuggestionService:
    """Generate and persist a coarse seven-class draft for one venue image."""

    def __init__(self, runtime: VenueVisionRuntime | None = None) -> None:
        self._runtime = runtime

    def _active_runtime(self) -> VenueVisionRuntime:
        if self._runtime is None:
            try:
                self._runtime = VenueVisionRuntime.load()
            except (FileNotFoundError, KeyError, TypeError, ValueError, OSError) as exc:
                raise ValueError(
                    "BakeSmart venue suggestion model is unavailable. "
                    "Train or restore the venue_vision_bootstrap_v1 checkpoint first."
                ) from exc
        return self._runtime

    def suggest(
        self,
        *,
        workspace: AnnotationWorkspace,
        dataset_key: str,
        scene_id: str,
        annotator_id: str | None = None,
        replace_existing: bool = False,
    ) -> dict[str, object]:
        image_path = workspace.image_path(dataset_key, scene_id)
        mask_path = workspace.mask_path(dataset_key, scene_id)
        existing_record = workspace.load_record(dataset_key, scene_id)
        if existing_record and existing_record.get("status") == "annotation_complete_pending_review":
            raise ValueError(
                "This annotation is already complete and pending review; "
                "a model suggestion cannot replace it."
            )
        if mask_path.is_file() and not replace_existing:
            raise ValueError(
                "This scene already has a draft mask. Confirm replacement before requesting a suggestion."
            )

        runtime = self._active_runtime()
        with Image.open(image_path) as source:
            oriented = ImageOps.exif_transpose(source).convert("RGB")
            width, height = oriented.size
            model_image = np.asarray(
                oriented.resize(
                    (runtime.image_size, runtime.image_size),
                    Image.Resampling.BILINEAR,
                ),
                dtype=np.uint8,
            )

        probabilities = runtime.model.predict_proba(extract_pixel_features(model_image))[
            "segmentation"
        ]
        expected_rows = runtime.image_size * runtime.image_size
        if probabilities.shape != (expected_rows, len(VENUE_LABELS)):
            raise ValueError("venue suggestion model returned an unexpected prediction shape")
        coarse_labels = np.argmax(probabilities, axis=1).astype(np.uint8).reshape(
            runtime.image_size,
            runtime.image_size,
        )
        full_labels = np.asarray(
            Image.fromarray(coarse_labels, mode="L").resize(
                (width, height),
                Image.Resampling.NEAREST,
            ),
            dtype=np.uint8,
        )
        stats = workspace.validate_labels(full_labels)
        normalized_annotator = workspace._normalize_annotator_id(  # noqa: SLF001
            annotator_id,
            required=False,
        )
        workspace._save_mask(dataset_key, scene_id, full_labels)  # noqa: SLF001
        record = workspace._record(  # noqa: SLF001
            dataset_key=dataset_key,
            scene_id=scene_id,
            annotator_id=normalized_annotator,
            status="draft_in_progress",
            annotation_completed_at=None,
        )
        record.update(
            {
                "annotation_method": "machine_assisted_draft",
                "suggestion_model_version": runtime.model_version,
                "suggestion_source": "synthetic_bootstrap_model",
                "suggestion_requires_human_correction": True,
                "training_status": "not_for_training",
            }
        )
        workspace._write_record(dataset_key, scene_id, record)  # noqa: SLF001
        self._write_provenance(
            workspace=workspace,
            dataset_key=dataset_key,
            scene_id=scene_id,
            record=record,
            stats=stats,
        )
        return {
            **stats,
            "status": "draft_in_progress",
            "record": record,
            "suggestion_model_version": runtime.model_version,
            "suggestion_source": "synthetic_bootstrap_model",
            "human_review_required": True,
        }

    @staticmethod
    def _write_provenance(
        *,
        workspace: AnnotationWorkspace,
        dataset_key: str,
        scene_id: str,
        record: dict[str, object],
        stats: dict[str, object],
    ) -> Path:
        base = workspace.record_path(dataset_key, scene_id)
        path = base.with_name(f"{scene_id}.suggestion.json")
        payload = {
            "schema_version": 1,
            "dataset": dataset_key,
            "scene_id": scene_id,
            "suggestion_source": record["suggestion_source"],
            "suggestion_model_version": record["suggestion_model_version"],
            "image_sha256": record["image_sha256"],
            "suggested_mask_sha256": record["mask_sha256"],
            "generated_at": record["updated_at"],
            "class_counts": stats["class_counts"],
            "human_review_required": True,
            "training_status": "not_for_training",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.part")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path
