"""Read-only Door/Outlet visual-audit workspace for BakeSmart Step 4.

Only the locked train and validation scene memberships are exposed. Semantic
masks and the Step-3 split are never modified. Optional audit decisions are
stored in a separate diagnostics JSON file and have no training-gate effect.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from training.annotation_workspace import PROJECT_DIR
from training.real_venue_segmentation import (
    CLASS_NAMES,
    SplitSample,
    _validate_mask_values,
    load_locked_split_manifest,
    samples_for_split,
)
from training.semantic_annotation_workspace import SEMANTIC_LABEL_CLASSES


DEFAULT_MANIFEST = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "raw"
    / "real_v2"
    / "splits"
    / "split_manifest.json"
)
DEFAULT_AUDIT_STATE = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "raw"
    / "real_v2"
    / "diagnostics"
    / "rare_class_visual_audit.json"
)
RARE_CLASSES = {"door": 2, "outlet": 5}
AUDIT_DECISIONS = {"looks_correct", "label_issue", "unsure"}


@dataclass(frozen=True)
class RareComponent:
    class_name: str
    class_id: int
    component_index: int
    pixels: int
    x: int
    y: int
    width: int
    height: int

    def as_dict(self) -> dict[str, object]:
        return {
            "class_name": self.class_name,
            "class_id": self.class_id,
            "component_index": self.component_index,
            "pixels": self.pixels,
            "bbox": [self.x, self.y, self.width, self.height],
        }


class RareClassAuditWorkspace:
    def __init__(
        self,
        project_dir: Path = PROJECT_DIR,
        manifest_path: Path = DEFAULT_MANIFEST,
        audit_state_path: Path = DEFAULT_AUDIT_STATE,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.manifest_path = Path(manifest_path).resolve()
        self.audit_state_path = Path(audit_state_path).resolve()
        self.manifest = load_locked_split_manifest(
            self.manifest_path,
            project_dir=self.project_dir,
        )
        self.samples: dict[str, SplitSample] = {}
        for split in ("train", "validation"):
            for sample in samples_for_split(
                self.manifest,
                split,
                project_dir=self.project_dir,
                verify_hashes=True,
            ):
                self.samples[sample.scene_id] = sample
        # Deliberately no call for the locked test split.

    def list_scenes(self) -> list[dict[str, object]]:
        state = self._load_state()
        scenes: list[dict[str, object]] = []
        for sample in sorted(
            self.samples.values(), key=lambda item: (item.split, item.scene_id)
        ):
            labels = self._read_mask(sample)
            class_counts = {
                name: int(np.count_nonzero(labels == class_id))
                for name, class_id in RARE_CLASSES.items()
            }
            if not any(class_counts.values()):
                continue
            components = self.components(sample.scene_id)
            saved = state.get("scenes", {}).get(sample.scene_id, {})
            scenes.append(
                {
                    "scene_id": sample.scene_id,
                    "split": sample.split,
                    "door_pixels": class_counts["door"],
                    "outlet_pixels": class_counts["outlet"],
                    "door_components": sum(
                        1 for item in components if item.class_name == "door"
                    ),
                    "outlet_components": sum(
                        1 for item in components if item.class_name == "outlet"
                    ),
                    "components": [item.as_dict() for item in components],
                    "audit_decision": saved.get("decision", "pending"),
                    "audit_notes": saved.get("notes", ""),
                    "audit_updated_at": saved.get("updated_at"),
                }
            )
        return scenes

    def summary(self) -> dict[str, int]:
        scenes = self.list_scenes()
        counts = {decision: 0 for decision in AUDIT_DECISIONS}
        pending = 0
        for scene in scenes:
            decision = str(scene.get("audit_decision") or "pending")
            if decision in counts:
                counts[decision] += 1
            else:
                pending += 1
        return {
            "total": len(scenes),
            "pending": pending,
            "looks_correct": counts["looks_correct"],
            "label_issue": counts["label_issue"],
            "unsure": counts["unsure"],
        }

    def components(self, scene_id: str) -> list[RareComponent]:
        sample = self._sample(scene_id)
        labels = self._read_mask(sample)
        result: list[RareComponent] = []
        for class_name, class_id in RARE_CLASSES.items():
            binary = (labels == class_id).astype(np.uint8)
            count, _component_labels, stats, _centroids = cv2.connectedComponentsWithStats(
                binary,
                connectivity=8,
            )
            candidates: list[tuple[int, int, int, int, int]] = []
            for component_id in range(1, count):
                x = int(stats[component_id, cv2.CC_STAT_LEFT])
                y = int(stats[component_id, cv2.CC_STAT_TOP])
                width = int(stats[component_id, cv2.CC_STAT_WIDTH])
                height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
                pixels = int(stats[component_id, cv2.CC_STAT_AREA])
                candidates.append((pixels, x, y, width, height))
            candidates.sort(reverse=True)
            for component_index, (pixels, x, y, width, height) in enumerate(candidates):
                result.append(
                    RareComponent(
                        class_name=class_name,
                        class_id=class_id,
                        component_index=component_index,
                        pixels=pixels,
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                    )
                )
        return result

    def image_png(self, scene_id: str) -> bytes:
        sample = self._sample(scene_id)
        with Image.open(sample.image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        return self._png(image)

    def rare_overlay_png(self, scene_id: str) -> bytes:
        sample = self._sample(scene_id)
        image, labels = self._read_pair(sample)
        base = image.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        overlay_pixels = np.zeros((image.height, image.width, 4), dtype=np.uint8)
        for class_name, class_id in RARE_CLASSES.items():
            color = next(
                label.rgb for label in SEMANTIC_LABEL_CLASSES if label.class_id == class_id
            )
            selected = labels == class_id
            overlay_pixels[selected, :3] = color
            overlay_pixels[selected, 3] = 150
        overlay = Image.fromarray(overlay_pixels, mode="RGBA")
        composite = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(composite)
        for component in self.components(scene_id):
            color = "#FF9800" if component.class_name == "door" else "#EC407A"
            x1, y1 = component.x, component.y
            x2 = component.x + component.width - 1
            y2 = component.y + component.height - 1
            draw.rectangle((x1, y1, x2, y2), outline=color, width=max(2, image.width // 500))
        return self._png(composite.convert("RGB"))

    def crop_png(self, scene_id: str, class_name: str, component_index: int) -> bytes:
        normalized_class = class_name.strip().lower()
        if normalized_class not in RARE_CLASSES:
            raise ValueError("class must be door or outlet")
        component = next(
            (
                item
                for item in self.components(scene_id)
                if item.class_name == normalized_class
                and item.component_index == component_index
            ),
            None,
        )
        if component is None:
            raise KeyError("rare-class component not found")
        sample = self._sample(scene_id)
        image, labels = self._read_pair(sample)
        crop_box = self._padded_crop_box(image.size, component)
        crop = image.crop(crop_box).convert("RGBA")
        x0, y0, x1, y1 = crop_box
        local_labels = labels[y0:y1, x0:x1]
        color = next(
            label.rgb
            for label in SEMANTIC_LABEL_CLASSES
            if label.class_id == component.class_id
        )
        rgba = np.zeros((crop.height, crop.width, 4), dtype=np.uint8)
        selected = local_labels == component.class_id
        rgba[selected, :3] = color
        rgba[selected, 3] = 155
        composite = Image.alpha_composite(crop, Image.fromarray(rgba, mode="RGBA"))
        draw = ImageDraw.Draw(composite)
        local_x = component.x - x0
        local_y = component.y - y0
        outline = "#FF9800" if normalized_class == "door" else "#EC407A"
        draw.rectangle(
            (
                local_x,
                local_y,
                local_x + component.width - 1,
                local_y + component.height - 1,
            ),
            outline=outline,
            width=max(2, crop.width // 150),
        )
        return self._png(composite.convert("RGB"))

    def save_decision(
        self,
        scene_id: str,
        decision: str,
        notes: str | None = None,
    ) -> dict[str, object]:
        self._sample(scene_id)
        normalized = (decision or "").strip().lower()
        if normalized not in AUDIT_DECISIONS:
            raise ValueError("audit decision must be looks_correct, label_issue, or unsure")
        clean_notes = (notes or "").strip()
        if normalized == "label_issue" and not clean_notes:
            raise ValueError("notes are required when marking a label issue")
        state = self._load_state()
        state.setdefault("schema_version", 1)
        state.setdefault("dataset", "real_v2")
        state.setdefault("test_split_used", False)
        scenes = state.setdefault("scenes", {})
        scenes[scene_id] = {
            "split": self.samples[scene_id].split,
            "decision": normalized,
            "notes": clean_notes,
            "updated_at": self._utc_now(),
        }
        self._write_state(state)
        return {
            "scene_id": scene_id,
            **scenes[scene_id],
            "summary": self.summary(),
        }

    def _sample(self, scene_id: str) -> SplitSample:
        try:
            return self.samples[scene_id]
        except KeyError as exc:
            raise KeyError(
                "scene is not available in the train/validation rare-class audit"
            ) from exc

    def _read_mask(self, sample: SplitSample) -> np.ndarray:
        with Image.open(sample.mask_path) as source:
            labels = np.asarray(source.convert("L"), dtype=np.uint8)
        _validate_mask_values(labels, sample.scene_id)
        return labels

    def _read_pair(self, sample: SplitSample) -> tuple[Image.Image, np.ndarray]:
        with Image.open(sample.image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        labels = self._read_mask(sample)
        if labels.shape != (image.height, image.width):
            raise ValueError(f"image/mask dimensions differ for {sample.scene_id}")
        return image, labels

    @staticmethod
    def _padded_crop_box(
        image_size: tuple[int, int],
        component: RareComponent,
    ) -> tuple[int, int, int, int]:
        image_width, image_height = image_size
        object_extent = max(component.width, component.height)
        if component.class_name == "outlet":
            crop_size = max(160, object_extent * 8)
        else:
            crop_size = max(300, int(object_extent * 2.2))
        crop_size = min(crop_size, max(image_width, image_height))
        center_x = component.x + component.width // 2
        center_y = component.y + component.height // 2
        half = crop_size // 2
        left = max(0, center_x - half)
        top = max(0, center_y - half)
        right = min(image_width, left + crop_size)
        bottom = min(image_height, top + crop_size)
        left = max(0, right - crop_size)
        top = max(0, bottom - crop_size)
        return int(left), int(top), int(right), int(bottom)

    def _load_state(self) -> dict[str, object]:
        if not self.audit_state_path.is_file():
            return {
                "schema_version": 1,
                "dataset": "real_v2",
                "test_split_used": False,
                "scenes": {},
            }
        try:
            payload = json.loads(self.audit_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("rare-class audit state is unreadable") from exc
        if not isinstance(payload, dict):
            raise ValueError("rare-class audit state must be a JSON object")
        return payload

    def _write_state(self, state: dict[str, object]) -> None:
        self.audit_state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.audit_state_path.with_suffix(".json.part")
        temporary.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.audit_state_path)

    @staticmethod
    def _png(image: Image.Image) -> bytes:
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def _utc_now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
