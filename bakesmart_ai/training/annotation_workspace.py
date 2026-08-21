"""Local seven-class venue-mask annotation workspace for BakeSmart.

Draft masks use pixel value 255 for pixels that have not been labelled yet.
Only completed annotations may contain final class IDs 0-6. Raw masks and
annotation sidecars live under ignored ``data/venue_vision/raw`` directories
and are therefore not intended for Git commits.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


PROJECT_DIR = Path(__file__).resolve().parents[1]
UNLABELLED_ID = 255
MAX_MASK_DATA_URL_CHARS = 48_000_000
SCENE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
ANNOTATOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@+-]{0,79}$")
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class LabelClass:
    class_id: int
    key: str
    name: str
    hex_color: str

    @property
    def rgb(self) -> tuple[int, int, int]:
        value = self.hex_color.lstrip("#")
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


LABEL_CLASSES = (
    LabelClass(0, "wall", "Wall", "#E57373"),
    LabelClass(1, "floor", "Floor", "#64B5F6"),
    LabelClass(2, "door", "Door", "#FFB74D"),
    LabelClass(3, "window", "Window", "#4DD0E1"),
    LabelClass(4, "furniture", "Furniture", "#9575CD"),
    LabelClass(5, "outlet", "Outlet", "#F06292"),
    LabelClass(6, "walkway", "Walkway candidate", "#81C784"),
)
LABEL_IDS = tuple(label.class_id for label in LABEL_CLASSES)
PALETTE_RGB = np.asarray([label.rgb for label in LABEL_CLASSES], dtype=np.int16)


@dataclass(frozen=True)
class DatasetLocation:
    key: str
    label: str
    images_dir: Path
    masks_dir: Path
    records_dir: Path


class AnnotationWorkspace:
    """Read local venue images and persist draft/final masks safely."""

    def __init__(self, project_dir: Path = PROJECT_DIR) -> None:
        self.project_dir = Path(project_dir).resolve()
        raw = self.project_dir / "data" / "venue_vision" / "raw"
        self.datasets: dict[str, DatasetLocation] = {
            "real_v2": DatasetLocation(
                key="real_v2",
                label="Real venue candidates v2",
                images_dir=raw / "real_v2" / "images",
                masks_dir=raw / "real_v2" / "masks",
                records_dir=raw / "real_v2" / "annotation_records",
            ),
            "gemini_synthetic_v1": DatasetLocation(
                key="gemini_synthetic_v1",
                label="Gemini synthetic v1",
                images_dir=raw / "gemini_synthetic_v1" / "images",
                masks_dir=raw / "gemini_synthetic_v1" / "masks",
                records_dir=raw / "gemini_synthetic_v1" / "annotation_records",
            ),
        }

    def dataset_descriptors(self) -> list[dict[str, object]]:
        return [
            {
                "key": dataset.key,
                "label": dataset.label,
                "image_count": len(self._image_paths(dataset)),
            }
            for dataset in self.datasets.values()
        ]

    def list_scenes(self, dataset_key: str) -> list[dict[str, object]]:
        dataset = self._dataset(dataset_key)
        return [
            self.scene_descriptor(dataset_key, path.stem)
            for path in self._image_paths(dataset)
        ]

    def scene_descriptor(self, dataset_key: str, scene_id: str) -> dict[str, object]:
        image_path = self.image_path(dataset_key, scene_id)
        with Image.open(image_path) as source:
            corrected = ImageOps.exif_transpose(source)
            width, height = corrected.size
        mask_path = self.mask_path(dataset_key, scene_id)
        record = self.load_record(dataset_key, scene_id)
        status = record.get("status") if record else None
        if status is None:
            status = "draft_in_progress" if mask_path.is_file() else "not_started"
        return {
            "scene_id": scene_id,
            "dataset": dataset_key,
            "file_name": image_path.name,
            "pixel_width": width,
            "pixel_height": height,
            "has_mask": mask_path.is_file(),
            "status": status,
            "annotator_id": record.get("annotator_id") if record else None,
            "updated_at": record.get("updated_at") if record else None,
        }

    def image_path(self, dataset_key: str, scene_id: str) -> Path:
        dataset = self._dataset(dataset_key)
        self._validate_scene_id(scene_id)
        matches = [path for path in self._image_paths(dataset) if path.stem == scene_id]
        if not matches:
            raise FileNotFoundError(f"unknown scene: {scene_id}")
        if len(matches) > 1:
            raise ValueError(f"multiple images share scene ID {scene_id}")
        return matches[0]

    def mask_path(self, dataset_key: str, scene_id: str) -> Path:
        dataset = self._dataset(dataset_key)
        self._validate_scene_id(scene_id)
        return dataset.masks_dir / f"{scene_id}.png"

    def record_path(self, dataset_key: str, scene_id: str) -> Path:
        dataset = self._dataset(dataset_key)
        self._validate_scene_id(scene_id)
        return dataset.records_dir / f"{scene_id}.json"

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
        for label in LABEL_CLASSES:
            selected = labels == label.class_id
            rgba[selected, :3] = label.rgb
            rgba[selected, 3] = 255
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
            differences = flat_rgb[:, None, :] - PALETTE_RGB[None, :, :]
            distances = np.sum(differences * differences, axis=2)
            nearest = np.argmin(distances, axis=1)
            nearest_distance = distances[np.arange(distances.shape[0]), nearest]
            if np.any(nearest_distance > 12_000):
                raise ValueError(
                    "mask contains colors outside the BakeSmart seven-class palette"
                )
            labels[opaque] = nearest.astype(np.uint8)
        return labels

    def validate_labels(self, labels: np.ndarray) -> dict[str, object]:
        if labels.ndim != 2:
            raise ValueError("mask must be a single-channel label image")
        allowed = np.isin(
            labels,
            np.asarray(LABEL_IDS + (UNLABELLED_ID,), dtype=np.uint8),
        )
        if not bool(np.all(allowed)):
            raise ValueError("mask contains label IDs outside 0-6 and 255")
        total_pixels = int(labels.size)
        unlabelled_pixels = int(np.count_nonzero(labels == UNLABELLED_ID))
        class_counts = {
            label.key: int(np.count_nonzero(labels == label.class_id))
            for label in LABEL_CLASSES
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
        labels = self.decode_overlay(dataset_key, scene_id, encoded_png)
        stats = self.validate_labels(labels)
        normalized_annotator = self._normalize_annotator_id(annotator_id, required=False)
        self._save_mask(dataset_key, scene_id, labels)
        record = self._record(
            dataset_key=dataset_key,
            scene_id=scene_id,
            annotator_id=normalized_annotator,
            status="draft_in_progress",
            annotation_completed_at=None,
        )
        self._write_record(dataset_key, scene_id, record)
        return {**stats, "status": record["status"], "record": record}

    def complete_annotation(
        self,
        dataset_key: str,
        scene_id: str,
        encoded_png: str,
        annotator_id: str,
    ) -> dict[str, object]:
        normalized_annotator = self._normalize_annotator_id(annotator_id, required=True)
        labels = self.decode_overlay(dataset_key, scene_id, encoded_png)
        stats = self.validate_labels(labels)
        if not stats["complete"]:
            raise ValueError(
                f"annotation still has {stats['unlabelled_pixels']} unlabelled pixel(s)"
            )
        existing = self.load_record(dataset_key, scene_id)
        if (
            existing
            and existing.get("status") == "annotation_complete_pending_review"
            and existing.get("annotator_id")
            and existing.get("annotator_id") != normalized_annotator
        ):
            raise ValueError(
                "a different annotator already completed this scene; use reviewer workflow instead"
            )
        self._save_mask(dataset_key, scene_id, labels)
        record = self._record(
            dataset_key=dataset_key,
            scene_id=scene_id,
            annotator_id=normalized_annotator,
            status="annotation_complete_pending_review",
            annotation_completed_at=self._utc_now(),
        )
        self._write_record(dataset_key, scene_id, record)
        return {**stats, "status": record["status"], "record": record}

    def load_record(self, dataset_key: str, scene_id: str) -> dict[str, object] | None:
        path = self.record_path(dataset_key, scene_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"annotation record is unreadable: {path.name}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"annotation record is invalid: {path.name}")
        return payload

    def _dataset(self, dataset_key: str) -> DatasetLocation:
        try:
            return self.datasets[dataset_key]
        except KeyError as exc:
            raise KeyError(f"unknown dataset: {dataset_key}") from exc

    @staticmethod
    def _image_paths(dataset: DatasetLocation) -> list[Path]:
        if not dataset.images_dir.is_dir():
            return []
        return sorted(
            path
            for path in dataset.images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        )

    @staticmethod
    def _validate_scene_id(scene_id: str) -> None:
        if not SCENE_ID_PATTERN.fullmatch(scene_id or ""):
            raise ValueError("scene ID contains unsupported characters")

    @staticmethod
    def _normalize_annotator_id(value: str | None, *, required: bool) -> str | None:
        normalized = (value or "").strip()
        if not normalized:
            if required:
                raise ValueError("annotator ID is required before completion")
            return None
        if not ANNOTATOR_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                "annotator ID must be 1-80 characters using letters, numbers, spaces, . _ @ + or -"
            )
        return normalized

    @staticmethod
    def _read_saved_mask(path: Path, expected_size: tuple[int, int]) -> np.ndarray:
        try:
            with Image.open(path) as source:
                if source.size != expected_size:
                    raise ValueError(
                        f"saved mask {path.name} does not match image dimensions"
                    )
                labels = np.asarray(source.convert("L"), dtype=np.uint8)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"saved mask is unreadable: {path.name}") from exc
        allowed = np.isin(
            labels,
            np.asarray(LABEL_IDS + (UNLABELLED_ID,), dtype=np.uint8),
        )
        if not bool(np.all(allowed)):
            raise ValueError(f"saved mask contains invalid class IDs: {path.name}")
        return labels

    def _save_mask(self, dataset_key: str, scene_id: str, labels: np.ndarray) -> Path:
        path = self.mask_path(dataset_key, scene_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".png.part")
        Image.fromarray(labels.astype(np.uint8), mode="L").save(temporary, format="PNG")
        temporary.replace(path)
        return path

    def _record(
        self,
        *,
        dataset_key: str,
        scene_id: str,
        annotator_id: str | None,
        status: str,
        annotation_completed_at: str | None,
    ) -> dict[str, object]:
        image_path = self.image_path(dataset_key, scene_id)
        mask_path = self.mask_path(dataset_key, scene_id)
        with Image.open(image_path) as source:
            width, height = ImageOps.exif_transpose(source).size
        existing = self.load_record(dataset_key, scene_id) or {}
        created_at = existing.get("created_at") or self._utc_now()
        return {
            "schema_version": 1,
            "dataset": dataset_key,
            "scene_id": scene_id,
            "image_path": self._relative(image_path),
            "mask_path": self._relative(mask_path),
            "pixel_width": width,
            "pixel_height": height,
            "image_sha256": self._sha256_file(image_path),
            "mask_sha256": self._sha256_file(mask_path),
            "annotator_id": annotator_id or existing.get("annotator_id"),
            "status": status,
            "created_at": created_at,
            "updated_at": self._utc_now(),
            "annotation_completed_at": annotation_completed_at,
            "reviewer_id": None,
            "review_completed_at": None,
            "review_status": "pending_independent_review"
            if status == "annotation_complete_pending_review"
            else "not_ready_for_review",
            "training_status": "not_for_training",
        }

    def _write_record(
        self,
        dataset_key: str,
        scene_id: str,
        record: dict[str, object],
    ) -> Path:
        path = self.record_path(dataset_key, scene_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.part")
        temporary.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_dir).as_posix()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def label_class_payload() -> list[dict[str, object]]:
    return [
        {
            "id": label.class_id,
            "key": label.key,
            "name": label.name,
            "color": label.hex_color,
        }
        for label in LABEL_CLASSES
    ]
