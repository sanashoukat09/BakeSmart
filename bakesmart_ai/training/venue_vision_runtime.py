"""Runtime for the synthetic-bootstrap venue segmentation checkpoint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from training.neural_network import MultiTaskMLP
from training.train_venue_vision import DEFAULT_VENUE_MODEL_DIR
from training.venue_vision_data import VENUE_LABELS, extract_pixel_features


MINIMUM_COMPONENT_FRACTION = {
    "wall": 0.08,
    "floor": 0.06,
    "door": 0.012,
    "window": 0.008,
    "furniture": 0.008,
    "outlet": 0.0003,
    "walkway": 0.025,
}


@dataclass(frozen=True)
class VenueVisionCandidate:
    label: str
    confidence: float
    bounding_box: tuple[float, float, float, float]
    area_fraction: float


class VenueVisionRuntime:
    def __init__(self, model: MultiTaskMLP, metadata: dict[str, object]) -> None:
        self.model = model
        self.metadata = metadata
        self.model_version = str(metadata["model_version"])
        self.image_size = int(metadata["data"]["image_size"])
        self.maximum_confidence = float(
            metadata["runtime_policy"]["maximum_reported_confidence"]
        )

    @classmethod
    def load(
        cls,
        model_dir: Path = DEFAULT_VENUE_MODEL_DIR,
    ) -> "VenueVisionRuntime":
        metadata = json.loads(
            (model_dir / "model_metadata.json").read_text(encoding="utf-8")
        )
        if metadata.get("production_approved") is not False:
            raise ValueError("venue bootstrap metadata truth flag is invalid")
        if metadata.get("pretrained_weights_used") is not False:
            raise ValueError("venue bootstrap may not use pretrained weights")
        architecture = metadata["architecture"]
        model = MultiTaskMLP.load(
            model_dir / metadata["artifacts"]["weights_file"],
            input_size=int(architecture["input_features"]),
            hidden_sizes=tuple(int(value) for value in architecture["hidden_sizes"]),
            output_sizes={"segmentation": len(VENUE_LABELS)},
            seed=int(metadata["initialization"]["seed"]),
        )
        return cls(model, metadata)

    def candidates(self, image: np.ndarray) -> list[VenueVisionCandidate]:
        if image.shape != (self.image_size, self.image_size, 3):
            raise ValueError(
                f"venue runtime expects {self.image_size}x{self.image_size} RGB"
            )
        probabilities = self.model.predict_proba(extract_pixel_features(image))[
            "segmentation"
        ]
        prediction = np.argmax(probabilities, axis=1).reshape(
            self.image_size, self.image_size
        )
        probability_map = probabilities.reshape(
            self.image_size,
            self.image_size,
            len(VENUE_LABELS),
        )
        candidates: list[VenueVisionCandidate] = []
        total_pixels = self.image_size * self.image_size
        for class_id, label in enumerate(VENUE_LABELS):
            minimum_pixels = max(
                1,
                round(MINIMUM_COMPONENT_FRACTION[label] * total_pixels),
            )
            for component in self._components(prediction == class_id):
                if len(component) < minimum_pixels:
                    continue
                rows = np.asarray([point[0] for point in component], dtype=np.int64)
                columns = np.asarray([point[1] for point in component], dtype=np.int64)
                raw_confidence = float(
                    np.mean(probability_map[rows, columns, class_id])
                )
                left = int(columns.min())
                top = int(rows.min())
                right = int(columns.max()) + 1
                bottom = int(rows.max()) + 1
                candidates.append(
                    VenueVisionCandidate(
                        label=label,
                        confidence=round(
                            min(raw_confidence, self.maximum_confidence),
                            4,
                        ),
                        bounding_box=(
                            round(left / self.image_size, 4),
                            round(top / self.image_size, 4),
                            round((right - left) / self.image_size, 4),
                            round((bottom - top) / self.image_size, 4),
                        ),
                        area_fraction=round(len(component) / total_pixels, 4),
                    )
                )
        candidates.sort(
            key=lambda candidate: (
                candidate.confidence,
                candidate.area_fraction,
                candidate.label,
            ),
            reverse=True,
        )
        return candidates[:10]

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
