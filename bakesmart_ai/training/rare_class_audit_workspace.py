"""Read-only Door/Outlet visual-audit workspace for BakeSmart Step 4.

Only the locked train and validation scene memberships are exposed. Semantic
masks and the Step-3 split are never modified. Optional audit decisions are
stored in a separate diagnostics JSON file and have no training-gate effect.

The scene list is intentionally lightweight: it uses split-manifest metadata
instead of scanning every full-resolution mask. Expensive mask/component work
is done lazily only for the scene currently being inspected.
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
DEFAULT_REPAIRED_ROOT = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
)
RARE_CLASSES = {"door": 2, "outlet": 5}
AUDIT_DECISIONS = {"looks_correct", "label_issue", "unsure"}
MAX_ZOOM_COMPONENTS_PER_CLASS = 12


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
        dataset_root: Path | None = None,
        dataset_name: str = "real_v2",
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.manifest_path = Path(manifest_path).resolve()
        self.audit_state_path = Path(audit_state_path).resolve()
        self.dataset_root = Path(dataset_root).resolve() if dataset_root else None
        self.dataset_name = dataset_name
        self.manifest = load_locked_split_manifest(
            self.manifest_path,
            project_dir=self.project_dir,
        )
        self.samples: dict[str, SplitSample] = {}
        if self.dataset_root is None:
            for split in ("train", "validation"):
                for sample in samples_for_split(
                    self.manifest,
                    split,
                    project_dir=self.project_dir,
                    verify_hashes=True,
                ):
                    self.samples[sample.scene_id] = sample
        else:
            for row in self.manifest["scenes"]:
                split = str(row.get("split") or "")
                if split not in {"train", "validation"}:
                    continue
                scene_id = str(row["scene_id"])
                image_path = self.dataset_root / "images" / f"{scene_id}.jpg"
                mask_path = self.dataset_root / "masks" / f"{scene_id}.png"
                if not image_path.is_file() or not mask_path.is_file():
                    raise ValueError(f"repaired image/mask pair is missing: {scene_id}")
                self.samples[scene_id] = SplitSample(
                    scene_id=scene_id,
                    split=split,
                    image_path=image_path,
                    mask_path=mask_path,
                    image_sha256="",
                    mask_sha256="",
                )
        # Deliberately no call for the locked test split.

        self._manifest_rows = {
            str(row["scene_id"]): row
            for row in self.manifest["scenes"]
            if row.get("split") in {"train", "validation"}
        }
        self._rare_presence_cache: dict[str, tuple[bool, bool]] = {}
        self._component_cache: dict[str, list[RareComponent]] = {}
        self._detail_cache: dict[str, dict[str, object]] = {}

    def list_scenes(self) -> list[dict[str, object]]:
        """Return fast scene metadata without opening image or mask files."""
        state = self._load_state()
        scenes: list[dict[str, object]] = []
        for sample in sorted(
            self.samples.values(), key=lambda item: (item.split, item.scene_id)
        ):
            manifest_row = self._manifest_rows.get(sample.scene_id, {})
            class_ids = manifest_row.get("class_ids_present")
            if self.dataset_root is not None:
                has_door, has_outlet = self._rare_presence(sample)
                if not (has_door or has_outlet):
                    continue
            elif isinstance(class_ids, list):
                present_ids = {int(value) for value in class_ids}
                has_door = RARE_CLASSES["door"] in present_ids
                has_outlet = RARE_CLASSES["outlet"] in present_ids
                if not (has_door or has_outlet):
                    continue
            else:
                # Older/synthetic manifests may not expose class presence.
                # Keep the scene visible rather than forcing a full-mask scan.
                has_door = True
                has_outlet = True

            saved = state.get("scenes", {}).get(sample.scene_id, {})
            scenes.append(
                {
                    "scene_id": sample.scene_id,
                    "split": sample.split,
                    "has_door": has_door,
                    "has_outlet": has_outlet,
                    "audit_decision": saved.get("decision", "pending"),
                    "audit_notes": saved.get("notes", ""),
                    "audit_updated_at": saved.get("updated_at"),
                }
            )
        return scenes

    def _rare_presence(self, sample: SplitSample) -> tuple[bool, bool]:
        cached = self._rare_presence_cache.get(sample.scene_id)
        if cached is not None:
            return cached
        labels = self._read_mask(sample)
        present_ids = {int(value) for value in np.unique(labels)}
        result = (
            RARE_CLASSES["door"] in present_ids,
            RARE_CLASSES["outlet"] in present_ids,
        )
        self._rare_presence_cache[sample.scene_id] = result
        return result

    def scene_detail(self, scene_id: str) -> dict[str, object]:
        """Analyze only the requested scene and cache the result in memory."""
        if scene_id in self._detail_cache:
            return dict(self._detail_cache[scene_id])

        sample = self._sample(scene_id)
        labels = self._read_mask(sample)
        counts = {
            name: int(np.count_nonzero(labels == class_id))
            for name, class_id in RARE_CLASSES.items()
        }
        all_components = self.components(scene_id)
        display_components: list[RareComponent] = []
        total_components: dict[str, int] = {}
        for class_name in RARE_CLASSES:
            class_components = [
                item for item in all_components if item.class_name == class_name
            ]
            total_components[class_name] = len(class_components)
            display_components.extend(
                class_components[:MAX_ZOOM_COMPONENTS_PER_CLASS]
            )

        detail = {
            "scene_id": scene_id,
            "split": sample.split,
            "door_pixels": counts["door"],
            "outlet_pixels": counts["outlet"],
            "door_components": total_components["door"],
            "outlet_components": total_components["outlet"],
            "components_shown_limit_per_class": MAX_ZOOM_COMPONENTS_PER_CLASS,
            "components": [item.as_dict() for item in display_components],
        }
        self._detail_cache[scene_id] = detail
        return dict(detail)

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
        if scene_id in self._component_cache:
            return list(self._component_cache[scene_id])

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
        self._component_cache[scene_id] = result
        return list(result)

    def image_png(self, scene_id: str) -> bytes:
        sample = self._sample(scene_id)
        with Image.open(sample.image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        return self._png(image)

    def rare_overlay_png(self, scene_id: str) -> bytes:
        sample = self._sample(scene_id)
        image, labels = self._read_pair(sample)
        base = image.convert("RGBA")
        overlay_pixels = np.zeros((image.height, image.width, 4), dtype=np.uint8)
        for class_id in RARE_CLASSES.values():
            color = next(
                label.rgb for label in SEMANTIC_LABEL_CLASSES if label.class_id == class_id
            )
            selected = labels == class_id
            overlay_pixels[selected, :3] = color
            overlay_pixels[selected, 3] = 150
        overlay = Image.fromarray(overlay_pixels, mode="RGBA")
        composite = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(composite)
        # Draw only the largest components; all rare pixels remain visible in the overlay.
        detail = self.scene_detail(scene_id)
        for component_data in detail["components"]:
            x, y, width, height = component_data["bbox"]
            color = "#FF9800" if component_data["class_name"] == "door" else "#EC407A"
            draw.rectangle(
                (x, y, x + width - 1, y + height - 1),
                outline=color,
                width=max(2, image.width // 500),
            )
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
        state.setdefault("dataset", self.dataset_name)
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
                "dataset": self.dataset_name,
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
