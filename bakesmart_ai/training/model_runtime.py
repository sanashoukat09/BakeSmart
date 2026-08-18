"""Load and run the locally trained BakeSmart bootstrap model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from training.neural_network import MultiTaskMLP
from training.train_model import DEFAULT_MODEL_DIR


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class BootstrapModelRuntime:
    """Verified local checkpoint loader; raw request mapping arrives in Phase 6."""

    def __init__(
        self,
        model: MultiTaskMLP,
        labels_by_head: dict[str, list[str]],
        feature_columns: list[str],
        metadata: dict[str, object],
    ) -> None:
        self.model = model
        self.labels_by_head = labels_by_head
        self.feature_columns = feature_columns
        self.metadata = metadata

    @classmethod
    def load(cls, model_dir: Path = DEFAULT_MODEL_DIR) -> "BootstrapModelRuntime":
        metadata_path = model_dir / "model_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        weights_path = model_dir / metadata["artifacts"]["weights_file"]
        if _sha256(weights_path) != metadata["artifacts"]["weights_sha256"]:
            raise ValueError("model weight checksum does not match model metadata")

        architecture = metadata["architecture"]
        model = MultiTaskMLP.load(
            weights_path,
            input_size=int(architecture["input_size"]),
            hidden_sizes=tuple(int(value) for value in architecture["hidden_sizes"]),
            output_sizes={
                name: int(size) for name, size in architecture["output_sizes"].items()
            },
            seed=int(metadata["initialization"]["seed"]),
        )
        label_mappings = metadata["data"]["target_label_to_id"]
        source_by_head = {
            "target__theme": "theme_label",
            "target__cake": "cake_label",
            "target__decor": "decor_label",
            "target__layout": "layout_label",
        }
        labels_by_head: dict[str, list[str]] = {}
        for head, source_field in source_by_head.items():
            labels_by_head[head] = [
                label
                for label, _ in sorted(
                    label_mappings[source_field].items(), key=lambda item: item[1]
                )
            ]
        return cls(
            model=model,
            labels_by_head=labels_by_head,
            feature_columns=list(metadata["data"]["feature_columns"]),
            metadata=metadata,
        )

    def predict(self, features: np.ndarray) -> list[dict[str, dict[str, float | str]]]:
        features = np.asarray(features, dtype=np.float64)
        if features.ndim != 2 or features.shape[1] != len(self.feature_columns):
            raise ValueError(
                f"expected a two-dimensional matrix with {len(self.feature_columns)} features"
            )
        probabilities = self.model.predict_proba(features)
        results: list[dict[str, dict[str, float | str]]] = []
        for row_index in range(features.shape[0]):
            result: dict[str, dict[str, float | str]] = {}
            for head, values in probabilities.items():
                class_id = int(np.argmax(values[row_index]))
                result[head.removeprefix("target__")] = {
                    "label": self.labels_by_head[head][class_id],
                    "confidence": float(values[row_index, class_id]),
                }
            results.append(result)
        return results
