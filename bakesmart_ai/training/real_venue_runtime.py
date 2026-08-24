"""Inference runtime for BakeSmart's frozen six-class real venue model."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyTorch is required for the real venue runtime") from exc

from training.annotation_workspace import PROJECT_DIR
from training.freeze_real_venue_model import DEFAULT_SELECTED_DIR, load_json
from training.real_venue_model_evaluation import (
    letterbox_image,
    load_checkpoint_model,
    predict_logits,
)
from training.real_venue_segmentation import CLASS_NAMES, sha256_file
from training.venue_vision_runtime import VenueVisionCandidate


MINIMUM_COMPONENT_FRACTION = {
    "wall": 0.06,
    "floor": 0.04,
    "door": 0.006,
    "window": 0.006,
    "furniture": 0.006,
    "outlet": 0.00008,
    "walkway": 0.02,
}


class RealVenueSegmentationRuntime:
    def __init__(
        self,
        *,
        model: torch.nn.Module,
        selection: dict[str, object],
        device: torch.device,
    ) -> None:
        self.model = model
        self.selection = selection
        self.device = device
        self.model_version = str(selection["model_version"])
        inference = selection["inference"]
        self.canvas_size = int(inference["canvas_size"])
        self.tile_size = int(inference["tile_size"])
        self.tile_stride = int(inference["tile_stride"])
        self.maximum_confidence = min(
            float(inference["maximum_reported_confidence"]), 0.49
        )

    @classmethod
    def load(
        cls,
        selected_dir: Path = DEFAULT_SELECTED_DIR,
        *,
        device_name: str = "cpu",
    ) -> "RealVenueSegmentationRuntime":
        selected_dir = Path(selected_dir).resolve()
        selection = load_json(
            selected_dir / "model_selection.json", "frozen model selection"
        )
        final_report = load_json(
            selected_dir / "locked_test_report.json", "locked-test report"
        )
        if final_report.get("status") != "final_locked_test_complete":
            raise ValueError("real venue model has no completed locked-test report")
        if final_report.get("test_split_used") is not True:
            raise ValueError("locked-test report truth flag is invalid")
        if final_report.get("model_version") != selection.get("model_version"):
            raise ValueError("locked-test report belongs to another model")
        if final_report.get("checkpoint_sha256") != selection.get("checkpoint_sha256"):
            raise ValueError("locked-test checkpoint checksum does not match selection")
        checkpoint_path = PROJECT_DIR / str(selection["checkpoint"])
        if sha256_file(checkpoint_path) != selection.get("checkpoint_sha256"):
            raise ValueError("frozen runtime checkpoint checksum is invalid")
        manifest_path = PROJECT_DIR / str(selection["split_manifest"])
        manifest_sha = sha256_file(manifest_path)
        if manifest_sha != selection.get("split_manifest_sha256"):
            raise ValueError("runtime split manifest checksum is invalid")
        if device_name not in {"cpu", "cuda"}:
            raise ValueError("runtime device must be cpu or cuda")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA runtime requested but unavailable")
        device = torch.device(device_name)
        model, _checkpoint = load_checkpoint_model(
            checkpoint_path,
            device=device,
            expected_manifest_sha256=manifest_sha,
        )
        return cls(model=model, selection=selection, device=device)

    @torch.no_grad()
    def candidates(self, image: Image.Image) -> list[VenueVisionCandidate]:
        tensor, transform = letterbox_image(image, canvas_size=self.canvas_size)
        logits = predict_logits(
            self.model,
            tensor,
            device=self.device,
            tile_size=self.tile_size,
            tile_stride=self.tile_stride,
        )
        probabilities = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()
        prediction = np.argmax(probabilities, axis=0)
        top = transform.top
        left = transform.left
        bottom = top + transform.resized_height
        right = left + transform.resized_width
        prediction = prediction[top:bottom, left:right]
        probabilities = probabilities[:, top:bottom, left:right]
        height, width = prediction.shape
        total_pixels = max(1, height * width)

        candidates: list[VenueVisionCandidate] = []
        floor_components: list[list[tuple[int, int]]] = []
        for class_id, label in enumerate(CLASS_NAMES):
            components = self._components(prediction == class_id)
            components.sort(key=len, reverse=True)
            if label == "floor":
                floor_components = components
            minimum = max(
                1,
                round(MINIMUM_COMPONENT_FRACTION[label] * total_pixels),
            )
            for component in components[:2]:
                if len(component) < minimum:
                    continue
                candidates.append(
                    self._candidate(
                        label,
                        class_id,
                        component,
                        probabilities,
                        width,
                        height,
                        confidence_scale=1.0,
                    )
                )

        walkway_minimum = max(
            1, round(MINIMUM_COMPONENT_FRACTION["walkway"] * total_pixels)
        )
        for component in floor_components[:1]:
            lower_floor = [point for point in component if point[0] >= height * 0.45]
            if len(lower_floor) >= walkway_minimum:
                candidates.append(
                    self._candidate(
                        "walkway",
                        CLASS_NAMES.index("floor"),
                        lower_floor,
                        probabilities,
                        width,
                        height,
                        confidence_scale=0.80,
                    )
                )

        # Retain the strongest region per class first, then fill remaining slots.
        candidates.sort(
            key=lambda item: (item.confidence, item.area_fraction), reverse=True
        )
        selected: list[VenueVisionCandidate] = []
        seen_labels: set[str] = set()
        for candidate in candidates:
            if candidate.label not in seen_labels:
                selected.append(candidate)
                seen_labels.add(candidate.label)
        for candidate in candidates:
            if candidate not in selected and len(selected) < 10:
                selected.append(candidate)
        return selected[:10]

    def _candidate(
        self,
        label: str,
        class_id: int,
        component: list[tuple[int, int]],
        probabilities: np.ndarray,
        width: int,
        height: int,
        *,
        confidence_scale: float,
    ) -> VenueVisionCandidate:
        rows = np.asarray([point[0] for point in component], dtype=np.int64)
        columns = np.asarray([point[1] for point in component], dtype=np.int64)
        confidence = float(np.mean(probabilities[class_id, rows, columns]))
        confidence = min(confidence * confidence_scale, self.maximum_confidence)
        x0, x1 = int(columns.min()), int(columns.max()) + 1
        y0, y1 = int(rows.min()), int(rows.max()) + 1
        return VenueVisionCandidate(
            label=label,
            confidence=round(max(0.0, confidence), 4),
            bounding_box=(
                round(x0 / width, 4),
                round(y0 / height, 4),
                round((x1 - x0) / width, 4),
                round((y1 - y0) / height, 4),
            ),
            area_fraction=round(len(component) / (width * height), 4),
        )

    @staticmethod
    def _components(binary: np.ndarray) -> list[list[tuple[int, int]]]:
        height, width = binary.shape
        visited = np.zeros_like(binary, dtype=bool)
        components: list[list[tuple[int, int]]] = []
        for row in range(height):
            for column in range(width):
                if not binary[row, column] or visited[row, column]:
                    continue
                visited[row, column] = True
                stack = [(row, column)]
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
