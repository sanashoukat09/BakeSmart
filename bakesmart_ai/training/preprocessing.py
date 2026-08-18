"""Leakage-safe preprocessing for the BakeSmart recommendation dataset."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Iterable, Mapping


NUMERIC_FEATURES = (
    "guest_count",
    "room_length_m",
    "room_width_m",
    "room_area_m2",
    "budget_pkr",
    "budget_per_guest_pkr",
    "space_per_guest_m2",
    "budget_per_area_pkr",
)

CATEGORICAL_FEATURES = (
    "event_type",
    "venue_type",
    "age_group",
    "time_of_day",
    "preferred_color",
    "preferred_style",
)

TARGET_FIELDS = {
    "theme_label": "target__theme",
    "cake_label": "target__cake",
    "decor_label": "target__decor",
    "layout_label": "target__layout",
}

UNKNOWN_CATEGORY = "__unknown__"


def _numeric_values(row: Mapping[str, str]) -> dict[str, float]:
    guest_count = float(row["guest_count"])
    room_area = float(row["room_area_m2"])
    budget = float(row["budget_pkr"])
    if guest_count <= 0 or room_area <= 0:
        raise ValueError("guest_count and room_area_m2 must be positive")
    return {
        "guest_count": guest_count,
        "room_length_m": float(row["room_length_m"]),
        "room_width_m": float(row["room_width_m"]),
        "room_area_m2": room_area,
        "budget_pkr": budget,
        "budget_per_guest_pkr": float(row["budget_per_guest_pkr"]),
        "space_per_guest_m2": room_area / guest_count,
        "budget_per_area_pkr": budget / room_area,
    }


def _format_float(value: float) -> str:
    if abs(value) < 5e-15:
        value = 0.0
    return format(value, ".12g")


@dataclass
class DatasetPreprocessor:
    """A small serializable preprocessor fitted only on training rows."""

    numeric_statistics: dict[str, dict[str, float]] = field(default_factory=dict)
    categorical_vocabularies: dict[str, list[str]] = field(default_factory=dict)
    target_label_to_id: dict[str, dict[str, int]] = field(default_factory=dict)
    fitted_row_count: int = 0
    fitted_split: str = "train"

    @property
    def fitted(self) -> bool:
        return bool(self.numeric_statistics and self.categorical_vocabularies)

    @property
    def feature_columns(self) -> list[str]:
        columns = [f"num__{field}" for field in NUMERIC_FEATURES]
        for field in CATEGORICAL_FEATURES:
            for value in self.categorical_vocabularies[field]:
                suffix = "unknown" if value == UNKNOWN_CATEGORY else value
                columns.append(f"cat__{field}__{suffix}")
        return columns

    @property
    def target_columns(self) -> list[str]:
        return list(TARGET_FIELDS.values())

    @property
    def output_columns(self) -> list[str]:
        return ["scenario_id", *self.feature_columns, *self.target_columns]

    def fit(self, rows: Iterable[Mapping[str, str]]) -> "DatasetPreprocessor":
        training_rows = list(rows)
        if not training_rows:
            raise ValueError("cannot fit preprocessing on an empty training split")
        if any(row.get("dataset_split") != "train" for row in training_rows):
            raise ValueError("preprocessing may only be fitted on rows marked train")

        numeric_columns: dict[str, list[float]] = {
            field: [] for field in NUMERIC_FEATURES
        }
        for row in training_rows:
            for field, value in _numeric_values(row).items():
                numeric_columns[field].append(value)

        self.numeric_statistics = {}
        for field, values in numeric_columns.items():
            mean = statistics.fmean(values)
            standard_deviation = statistics.pstdev(values)
            if not math.isfinite(mean) or standard_deviation <= 0:
                raise ValueError(f"numeric feature {field} has invalid statistics")
            self.numeric_statistics[field] = {
                "mean": mean,
                "standard_deviation": standard_deviation,
                "minimum": min(values),
                "maximum": max(values),
            }

        self.categorical_vocabularies = {}
        for field in CATEGORICAL_FEATURES:
            vocabulary = sorted({row[field] for row in training_rows})
            if not vocabulary or any(not value for value in vocabulary):
                raise ValueError(f"categorical feature {field} has an empty value")
            self.categorical_vocabularies[field] = [*vocabulary, UNKNOWN_CATEGORY]

        self.target_label_to_id = {}
        for field in TARGET_FIELDS:
            labels = sorted({row[field] for row in training_rows})
            if not labels or any(not label for label in labels):
                raise ValueError(f"target {field} has an empty label")
            self.target_label_to_id[field] = {
                label: index for index, label in enumerate(labels)
            }

        self.fitted_row_count = len(training_rows)
        return self

    def transform_row(self, row: Mapping[str, str]) -> dict[str, str]:
        if not self.fitted:
            raise ValueError("preprocessor must be fitted before transformation")

        transformed: dict[str, str] = {"scenario_id": row["scenario_id"]}
        numeric_values = _numeric_values(row)
        for field in NUMERIC_FEATURES:
            statistics_for_field = self.numeric_statistics[field]
            standardized = (
                numeric_values[field] - statistics_for_field["mean"]
            ) / statistics_for_field["standard_deviation"]
            transformed[f"num__{field}"] = _format_float(standardized)

        for field in CATEGORICAL_FEATURES:
            vocabulary = self.categorical_vocabularies[field]
            actual_value = row[field]
            selected = actual_value if actual_value in vocabulary else UNKNOWN_CATEGORY
            for value in vocabulary:
                suffix = "unknown" if value == UNKNOWN_CATEGORY else value
                transformed[f"cat__{field}__{suffix}"] = (
                    "1" if value == selected else "0"
                )

        for source_field, output_field in TARGET_FIELDS.items():
            label = row[source_field]
            if label not in self.target_label_to_id[source_field]:
                raise ValueError(f"target {source_field} contains unknown label {label!r}")
            transformed[output_field] = str(
                self.target_label_to_id[source_field][label]
            )
        return transformed

    def transform(self, rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
        return [self.transform_row(row) for row in rows]

    def to_dict(self) -> dict[str, object]:
        if not self.fitted:
            raise ValueError("cannot serialize an unfitted preprocessor")
        return {
            "preprocessor_version": "1.0.0",
            "fitted_split": self.fitted_split,
            "fitted_row_count": self.fitted_row_count,
            "numeric_features": list(NUMERIC_FEATURES),
            "numeric_statistics": self.numeric_statistics,
            "categorical_features": list(CATEGORICAL_FEATURES),
            "categorical_vocabularies": self.categorical_vocabularies,
            "unknown_category": UNKNOWN_CATEGORY,
            "feature_columns": self.feature_columns,
            "target_columns": self.target_columns,
            "target_label_to_id": self.target_label_to_id,
            "output_columns": self.output_columns,
        }
