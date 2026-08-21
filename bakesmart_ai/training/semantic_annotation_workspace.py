"""Six-class venue annotation workspace with a separate derived Walkway layer.

The legacy BakeSmart workspace used class 6 inside the semantic mask. This
workspace keeps semantic IDs 0-5 only and stores Walkway as a separate binary
PNG. Legacy masks containing class 6 remain readable: class 6 is interpreted as
Floor in memory but is not rewritten unless the user explicitly saves the scene.
"""

from __future__ import annotations

import base64
import binascii
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from training.annotation_workspace import (
    ANNOTATOR_ID_PATTERN,
    MAX_MASK_DATA_URL_CHARS,
    PROJECT_DIR,
    AnnotationWorkspace,
    LabelClass,
    UNLABELLED_ID,
)
from training.walkway_generator import derive_walkway_candidate


SEMANTIC_LABEL_CLASSES = (
    LabelClass(0, "wall", "Wall", "#E57373"),
    LabelClass(1, "floor", "Floor", "#64B5F6"),
    LabelClass(2, "door", "Door", "#FFB74D"),
    LabelClass(3, "window", "Window", "#4DD0E1"),
    LabelClass(4, "furniture", "Furniture", "#9575CD"),
    LabelClass(5, "outlet", "Outlet", "#F06292"),
)
SEMANTIC_LABEL_IDS = tuple(label.class_id for label in SEMANTIC_LABEL_CLASSES)
SEMANTIC_PALETTE_RGB = np.asarray(
    [label.rgb for label in SEMANTIC_LABEL_CLASSES], dtype=np.int16
)
WALKWAY_RGB = (129, 199, 132)


class SemanticAnnotationWorkspace(AnnotationWorkspace):
    """Annotation workspace for six semantic classes plus binary Walkway."""

    def __init__(self, project_dir: Path = PROJECT_DIR) -> None:
        super().__init__(project_dir)

    def walkway_path(self, dataset_key: str, scene_id: str) -> Path:
        dataset = self._dataset(dataset_key)
        self._validate_scene_id(scene_id)
        return dataset.masks_dir.parent / "walkway_masks" / f"{scene_id}.png"

    def scene_descriptor(self, dataset_key: str, scene_id: str) -> dict[str, object]:
        descriptor = super().scene_descriptor(dataset_key, scene_id)
        descriptor["has_walkway_mask"] = self.walkway_path(dataset_key, scene_id).is_file()
        return descriptor

    def overlay_png(self, dataset_key: str, scene_id: str) -> bytes:
        image_path = self.image_path(dataset_key, scene_id)
        with Image.open(image_path) as source:
            width, height = ImageOps.exif_transpose(source).size
        mask_path = self.mask_path(dataset_key, scene_id)
        if mask_path.is_file():
            labels = self._read_saved_mask(mask_path, (width, height))
        else:
            labels = np.full((height, width), UNLABELLED_ID, dtype=np.uint8)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        for label in SEMANTIC_LABEL_CLASSES:
            selected = labels == label.class_id
            rgba[selected, :3] = label.rgb
            rgba[selected, 3] = 255
        output = io.BytesIO()
        Image.fromarray(rgba, mode="RGBA").save(output, format="PNG")
        return output.getvalue()

    def walkway_overlay_png(self, dataset_key: str, scene_id: str) -> bytes:
        image_path = self.image_path(dataset_key, scene_id)
        with Image.open(image_path) as source:
            width, height = ImageOps.exif_transpose(source).size
        path = self.walkway_path(dataset_key, scene_id)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        if path.is_file():
            walkway = self._read_walkway_mask(path, (width, height))
            selected = walkway == 1
            rgba[selected, :3] = WALKWAY_RGB
            rgba[selected, 3] = 170
        output = io.BytesIO()
        Image.fromarray(rgba, mode="RGBA").save(output, format="PNG")
        return output.getvalue()

    def decode_overlay(self, dataset_key: str, scene_id: str, encoded_png: str) -> np.ndarray:
        if not encoded_png or len(encoded_png) > MAX_MASK_DATA_URL_CHARS:
            raise ValueError("mask payload is empty or too large")
        payload = encoded_png.strip()
        if payload.startswith("data:"):
            prefix, separator, payload = payload.partition(",")
            if not separator or "image/png" not in prefix.lower():
                raise ValueError("mask payload must be a PNG data URL")
        try:
            raw = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("mask payload is not valid base64") from exc
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.format != "PNG":
                    raise ValueError("mask payload must contain PNG image data")
                rgba = np.asarray(source.convert("RGBA"), dtype=np.uint8)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("mask payload is not a readable PNG") from exc

        image_path = self.image_path(dataset_key, scene_id)
        with Image.open(image_path) as source:
            expected_width, expected_height = ImageOps.exif_transpose(source).size
        if rgba.shape[:2] != (expected_height, expected_width):
            raise ValueError(
                "mask dimensions must exactly match the source image "
                f"({expected_width}x{expected_height})"
            )

        labels = np.full((expected_height, expected_width), UNLABELLED_ID, dtype=np.uint8)
        opaque = rgba[..., 3] >= 16
        if np.any(opaque):
            rgb = rgba[..., :3].astype(np.int16)
            flat_rgb = rgb[opaque]
            differences = flat_rgb[:, None, :] - SEMANTIC_PALETTE_RGB[None, :, :]
            distances = np.sum(differences * differences, axis=2)
            nearest = np.argmin(distances, axis=1)
            nearest_distance = distances[np.arange(distances.shape[0]), nearest]
            if np.any(nearest_distance > 12_000):
                raise ValueError("mask contains colors outside the BakeSmart six-class palette")
            labels[opaque] = nearest.astype(np.uint8)
        return labels

    def validate_labels(self, labels: np.ndarray) -> dict[str, object]:
        if labels.ndim != 2:
            raise ValueError("mask must be a single-channel label image")
        allowed = np.isin(
            labels,
            np.asarray(SEMANTIC_LABEL_IDS + (UNLABELLED_ID,), dtype=np.uint8),
        )
        if not bool(np.all(allowed)):
            raise ValueError("semantic mask contains label IDs outside 0-5 and 255")
        total_pixels = int(labels.size)
        unlabelled_pixels = int(np.count_nonzero(labels == UNLABELLED_ID))
        class_counts = {
            label.key: int(np.count_nonzero(labels == label.class_id))
            for label in SEMANTIC_LABEL_CLASSES
        }
        return {
            "complete": unlabelled_pixels == 0,
            "total_pixels": total_pixels,
            "labelled_pixels": total_pixels - unlabelled_pixels,
            "unlabelled_pixels": unlabelled_pixels,
            "coverage_fraction": round(
                (total_pixels - unlabelled_pixels) / max(total_pixels, 1), 6
            ),
            "class_counts": class_counts,
        }

    def save_draft(
        self,
        dataset_key: str,
        scene_id: str,
        encoded_png: str,
        annotator_id: str | None = None,
    ) -> dict[str, object]:
        result = super().save_draft(dataset_key, scene_id, encoded_png, annotator_id)
        labels = self._read_saved_mask(
            self.mask_path(dataset_key, scene_id),
            self._image_size(dataset_key, scene_id),
        )
        walkway = self.regenerate_walkway(dataset_key, scene_id, labels)
        result["walkway_pixels"] = walkway["walkway_pixels"]
        return result

    def complete_annotation(
        self,
        dataset_key: str,
        scene_id: str,
        encoded_png: str,
        annotator_id: str,
    ) -> dict[str, object]:
        result = super().complete_annotation(dataset_key, scene_id, encoded_png, annotator_id)
        labels = self._read_saved_mask(
            self.mask_path(dataset_key, scene_id),
            self._image_size(dataset_key, scene_id),
        )
        walkway = self.regenerate_walkway(dataset_key, scene_id, labels)
        result["walkway_pixels"] = walkway["walkway_pixels"]
        return result

    def regenerate_walkway(
        self,
        dataset_key: str,
        scene_id: str,
        labels: np.ndarray | None = None,
    ) -> dict[str, object]:
        if labels is None:
            labels = self._read_saved_mask(
                self.mask_path(dataset_key, scene_id),
                self._image_size(dataset_key, scene_id),
            )
        result = derive_walkway_candidate(labels)
        self._save_walkway_mask(dataset_key, scene_id, result.walkway_mask)
        return {
            "walkway_pixels": result.walkway_pixels,
            "clearance_pixels": result.clearance_pixels,
            "walkway_fraction_of_floor": result.walkway_fraction_of_floor,
        }

    @staticmethod
    def _read_saved_mask(path: Path, expected_size: tuple[int, int]) -> np.ndarray:
        try:
            with Image.open(path) as source:
                if source.size != expected_size:
                    raise ValueError(f"saved mask {path.name} does not match image dimensions")
                labels = np.asarray(source.convert("L"), dtype=np.uint8).copy()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"saved mask is unreadable: {path.name}") from exc
        # Legacy class 6 meant Walkway and was carved out of Floor. For display
        # and any explicit future save, interpret those pixels as Floor.
        labels[labels == 6] = 1
        allowed = np.isin(
            labels,
            np.asarray(SEMANTIC_LABEL_IDS + (UNLABELLED_ID,), dtype=np.uint8),
        )
        if not bool(np.all(allowed)):
            raise ValueError(f"saved mask contains invalid semantic class IDs: {path.name}")
        return labels

    def _save_walkway_mask(self, dataset_key: str, scene_id: str, walkway: np.ndarray) -> Path:
        values = np.asarray(walkway, dtype=np.uint8)
        if values.ndim != 2 or not bool(np.all(np.isin(values, (0, 1)))):
            raise ValueError("walkway mask must be a single-channel binary 0/1 image")
        path = self.walkway_path(dataset_key, scene_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".png.part")
        Image.fromarray(values, mode="L").save(temporary, format="PNG")
        temporary.replace(path)
        return path

    @staticmethod
    def _read_walkway_mask(path: Path, expected_size: tuple[int, int]) -> np.ndarray:
        try:
            with Image.open(path) as source:
                if source.size != expected_size:
                    raise ValueError(f"walkway mask {path.name} does not match image dimensions")
                values = np.asarray(source.convert("L"), dtype=np.uint8)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"walkway mask is unreadable: {path.name}") from exc
        if not bool(np.all(np.isin(values, (0, 1)))):
            raise ValueError(f"walkway mask must contain only 0 and 1: {path.name}")
        return values

    def _image_size(self, dataset_key: str, scene_id: str) -> tuple[int, int]:
        with Image.open(self.image_path(dataset_key, scene_id)) as source:
            return ImageOps.exif_transpose(source).size

    def _record(
        self,
        *,
        dataset_key: str,
        scene_id: str,
        annotator_id: str | None,
        status: str,
        annotation_completed_at: str | None,
    ) -> dict[str, object]:
        record = super()._record(
            dataset_key=dataset_key,
            scene_id=scene_id,
            annotator_id=annotator_id,
            status=status,
            annotation_completed_at=annotation_completed_at,
        )
        record["semantic_schema_version"] = 2
        record["semantic_class_ids"] = list(SEMANTIC_LABEL_IDS)
        record["walkway_storage"] = "separate_binary_mask"
        walkway_path = self.walkway_path(dataset_key, scene_id)
        if walkway_path.is_file():
            record["walkway_mask_path"] = self._relative(walkway_path)
            record["walkway_mask_sha256"] = self._sha256_file(walkway_path)
        return record


def semantic_label_class_payload() -> list[dict[str, object]]:
    return [
        {
            "id": label.class_id,
            "key": label.key,
            "name": label.name,
            "color": label.hex_color,
        }
        for label in SEMANTIC_LABEL_CLASSES
    ]
