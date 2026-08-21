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

from training.annotation_workspace import AnnotationWorkspace, UNLABELLED_ID
from training.venue_vision_data import LABEL_TO_ID, VENUE_LABELS, extract_pixel_features
from training.venue_vision_runtime import VenueVisionRuntime


MAX_WORKING_LONG_EDGE = 512
CLASS_CONFIDENCE_THRESHOLDS = np.asarray(
    [0.24, 0.24, 0.34, 0.34, 0.28, 0.48, 0.36],
    dtype=np.float64,
)
SPECIAL_CLASS_LIMITS = {
    "door": (0.003, 0.28, 4),
    "window": (0.002, 0.22, 6),
    "outlet": (0.00002, 0.006, 6),
    "walkway": (0.008, 0.55, 3),
}


class MaskSuggestionService:
    """Generate and persist a conservative seven-class draft for one venue image."""

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
            working = self._working_image(oriented)

        working_pixels = np.asarray(working, dtype=np.uint8)
        work_height, work_width = working_pixels.shape[:2]
        probabilities = runtime.model.predict_proba(
            extract_pixel_features(working_pixels)
        )["segmentation"]
        expected_rows = work_height * work_width
        if probabilities.shape != (expected_rows, len(VENUE_LABELS)):
            raise ValueError("venue suggestion model returned an unexpected prediction shape")

        probability_map = probabilities.reshape(
            work_height,
            work_width,
            len(VENUE_LABELS),
        )
        smoothed = self._smooth_probabilities(probability_map)
        floor_boundary = self._estimate_floor_boundary(working_pixels)
        conservative = self._conservative_labels(smoothed, floor_boundary)
        full_labels = np.asarray(
            Image.fromarray(conservative, mode="L").resize(
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
                "suggestion_strategy": "high_resolution_conservative_v2",
                "suggestion_working_width": work_width,
                "suggestion_working_height": work_height,
                "suggestion_floor_boundary_ratio": round(
                    floor_boundary / max(work_height, 1), 4
                ),
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
            "suggestion_strategy": "high_resolution_conservative_v2",
            "working_size": [work_width, work_height],
            "human_review_required": True,
        }

    @staticmethod
    def _working_image(image: Image.Image) -> Image.Image:
        width, height = image.size
        long_edge = max(width, height)
        if long_edge <= MAX_WORKING_LONG_EDGE:
            return image.copy()
        scale = MAX_WORKING_LONG_EDGE / long_edge
        resized = (
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )
        return image.resize(resized, Image.Resampling.BILINEAR)

    @staticmethod
    def _smooth_probabilities(probabilities: np.ndarray) -> np.ndarray:
        height, width, _ = probabilities.shape
        padded = np.pad(probabilities, ((1, 1), (1, 1), (0, 0)), mode="edge")
        smoothed = np.zeros_like(probabilities, dtype=np.float64)
        for row_offset in range(3):
            for column_offset in range(3):
                smoothed += padded[
                    row_offset : row_offset + height,
                    column_offset : column_offset + width,
                ]
        return smoothed / 9.0

    @staticmethod
    def _estimate_floor_boundary(image: np.ndarray) -> int:
        height = image.shape[0]
        if height < 5:
            return max(1, round(height * 0.65))
        grayscale = np.mean(image.astype(np.float64), axis=2)
        transitions = np.mean(np.abs(np.diff(grayscale, axis=0)), axis=1)
        start = max(1, round(height * 0.45))
        stop = min(height - 1, max(start + 1, round(height * 0.88)))
        local = transitions[start:stop]
        if not local.size:
            return round(height * 0.65)
        boundary = start + int(np.argmax(local)) + 1
        return int(np.clip(boundary, round(height * 0.45), round(height * 0.88)))

    def _conservative_labels(
        self,
        probabilities: np.ndarray,
        floor_boundary: int,
    ) -> np.ndarray:
        height, width, _ = probabilities.shape
        labels = np.argmax(probabilities, axis=2).astype(np.uint8)
        confidence = np.max(probabilities, axis=2)
        row_grid = np.broadcast_to(np.arange(height)[:, None], (height, width))
        margin = max(2, round(height * 0.035))

        wall = LABEL_TO_ID["wall"]
        floor = LABEL_TO_ID["floor"]
        door = LABEL_TO_ID["door"]
        window = LABEL_TO_ID["window"]
        furniture = LABEL_TO_ID["furniture"]
        outlet = LABEL_TO_ID["outlet"]
        walkway = LABEL_TO_ID["walkway"]

        upper = row_grid < floor_boundary - margin
        lower = row_grid > floor_boundary + margin

        # Floor and walkway predictions in the clear upper-wall zone are usually
        # domain-shift mistakes from the synthetic bootstrap model.
        bad_upper = upper & np.isin(labels, [floor, walkway])
        self._reassign_to_best(
            labels,
            probabilities,
            bad_upper,
            (wall, furniture, door, window, outlet),
        )

        # Wall/window/outlet predictions well below the floor boundary are not
        # plausible. Door and furniture may legitimately cross the boundary.
        bad_lower = lower & np.isin(labels, [wall, window, outlet])
        self._reassign_to_best(
            labels,
            probabilities,
            bad_lower,
            (floor, furniture, door, walkway),
        )

        labels[(labels == window) & (row_grid >= floor_boundary)] = UNLABELLED_ID
        labels[(labels == walkway) & (row_grid < floor_boundary)] = UNLABELLED_ID

        # Remove implausibly large/tiny fragmented special-class regions. This
        # prevents the colourful speckling seen when the synthetic model is
        # applied directly to real photographs.
        for name, (minimum_fraction, maximum_fraction, max_components) in SPECIAL_CLASS_LIMITS.items():
            class_id = LABEL_TO_ID[name]
            self._filter_components(
                labels,
                probabilities,
                class_id=class_id,
                minimum_fraction=minimum_fraction,
                maximum_fraction=maximum_fraction,
                max_components=max_components,
                floor_boundary=floor_boundary,
            )

        safe_labels = labels.clip(0, len(VENUE_LABELS) - 1)
        thresholds = CLASS_CONFIDENCE_THRESHOLDS[safe_labels]
        uncertain = (labels != UNLABELLED_ID) & (confidence < thresholds)
        labels[uncertain] = UNLABELLED_ID
        return labels.astype(np.uint8)

    @staticmethod
    def _reassign_to_best(
        labels: np.ndarray,
        probabilities: np.ndarray,
        mask: np.ndarray,
        allowed_ids: tuple[int, ...],
    ) -> None:
        if not np.any(mask):
            return
        allowed = np.asarray(allowed_ids, dtype=np.int64)
        selected_probabilities = probabilities[mask][:, allowed]
        labels[mask] = allowed[np.argmax(selected_probabilities, axis=1)]

    def _filter_components(
        self,
        labels: np.ndarray,
        probabilities: np.ndarray,
        *,
        class_id: int,
        minimum_fraction: float,
        maximum_fraction: float,
        max_components: int,
        floor_boundary: int,
    ) -> None:
        components = self._components(labels == class_id)
        if not components:
            return
        total = labels.size
        scored: list[tuple[float, list[tuple[int, int]]]] = []
        for component in components:
            fraction = len(component) / total
            rows = np.fromiter((point[0] for point in component), dtype=np.int64)
            columns = np.fromiter((point[1] for point in component), dtype=np.int64)
            if fraction < minimum_fraction or fraction > maximum_fraction:
                labels[rows, columns] = UNLABELLED_ID
                continue
            if class_id == LABEL_TO_ID["outlet"] and float(np.mean(rows)) >= floor_boundary:
                labels[rows, columns] = UNLABELLED_ID
                continue
            if class_id == LABEL_TO_ID["walkway"] and float(np.mean(rows)) < floor_boundary:
                labels[rows, columns] = UNLABELLED_ID
                continue
            score = float(np.mean(probabilities[rows, columns, class_id])) * len(component)
            scored.append((score, component))

        scored.sort(key=lambda item: item[0], reverse=True)
        for _, component in scored[max_components:]:
            rows = np.fromiter((point[0] for point in component), dtype=np.int64)
            columns = np.fromiter((point[1] for point in component), dtype=np.int64)
            labels[rows, columns] = UNLABELLED_ID

    @staticmethod
    def _components(binary: np.ndarray) -> list[list[tuple[int, int]]]:
        height, width = binary.shape
        visited = np.zeros_like(binary, dtype=bool)
        components: list[list[tuple[int, int]]] = []
        for row in range(height):
            for column in range(width):
                if not binary[row, column] or visited[row, column]:
                    continue
                stack = [(row, column)]
                visited[row, column] = True
                component: list[tuple[int, int]] = []
                while stack:
                    current_row, current_column = stack.pop()
                    component.append((current_row, current_column))
                    for next_row, next_column in (
                        (current_row - 1, current_column),
                        (current_row + 1, current_column),
                        (current_row, current_column - 1),
                        (current_row, current_column + 1),
                    ):
                        if (
                            0 <= next_row < height
                            and 0 <= next_column < width
                            and binary[next_row, next_column]
                            and not visited[next_row, next_column]
                        ):
                            visited[next_row, next_column] = True
                            stack.append((next_row, next_column))
                components.append(component)
        return components

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
            "schema_version": 2,
            "dataset": dataset_key,
            "scene_id": scene_id,
            "suggestion_source": record["suggestion_source"],
            "suggestion_model_version": record["suggestion_model_version"],
            "suggestion_strategy": record["suggestion_strategy"],
            "suggestion_working_width": record["suggestion_working_width"],
            "suggestion_working_height": record["suggestion_working_height"],
            "suggestion_floor_boundary_ratio": record["suggestion_floor_boundary_ratio"],
            "image_sha256": record["image_sha256"],
            "suggested_mask_sha256": record["mask_sha256"],
            "generated_at": record["updated_at"],
            "class_counts": stats["class_counts"],
            "unlabelled_pixels": stats["unlabelled_pixels"],
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
