"""Load the numeric Phase 4 matrices for local model training."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from training.prepare_dataset import DEFAULT_OUTPUT_DIR


@dataclass(frozen=True)
class ModelSplit:
    name: str
    scenario_ids: tuple[str, ...]
    features: np.ndarray
    targets: dict[str, np.ndarray]

    @property
    def row_count(self) -> int:
        return self.features.shape[0]


def load_preprocessing_metadata(
    processed_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, object]:
    path = processed_dir / "preprocessing.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_model_split(
    split: str,
    processed_dir: Path = DEFAULT_OUTPUT_DIR,
    metadata: dict[str, object] | None = None,
) -> ModelSplit:
    if split not in {"train", "validation", "test"}:
        raise ValueError(f"unsupported split {split!r}")
    metadata = metadata or load_preprocessing_metadata(processed_dir)
    feature_columns = list(metadata["feature_columns"])
    target_columns = list(metadata["target_columns"])
    expected_columns = ["scenario_id", *feature_columns, *target_columns]

    path = processed_dir / f"{split}.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != expected_columns:
            raise ValueError(f"{split} matrix schema does not match preprocessing metadata")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{split} matrix is empty")

    features = np.asarray(
        [[float(row[column]) for column in feature_columns] for row in rows],
        dtype=np.float64,
    )
    targets = {
        column: np.asarray([int(row[column]) for row in rows], dtype=np.int64)
        for column in target_columns
    }
    if not np.isfinite(features).all():
        raise ValueError(f"{split} matrix contains non-finite features")
    return ModelSplit(
        name=split,
        scenario_ids=tuple(row["scenario_id"] for row in rows),
        features=features,
        targets=targets,
    )
