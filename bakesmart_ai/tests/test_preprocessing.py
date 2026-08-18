from __future__ import annotations

import csv
import json
import statistics
from copy import deepcopy
from pathlib import Path

import pytest

from training.prepare_dataset import prepare_dataset
from training.preprocessing import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    DatasetPreprocessor,
)
from training.validate_datasets import DEFAULT_DATA_DIR


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def _prepare(tmp_path: Path, name: str = "run") -> tuple[Path, dict[str, object]]:
    root = tmp_path / name
    output = root / "processed"
    report = prepare_dataset(
        output_dir=output,
        review_path=root / "review.csv",
        review_status_path=root / "review_status.json",
    )
    return output, report


def test_prepare_dataset_creates_locked_numeric_splits(tmp_path: Path) -> None:
    output, report = _prepare(tmp_path)

    assert report["splits"] == {"train": 1680, "validation": 360, "test": 360}
    assert report["leakage_audit"]["passed"] is True
    assert report["preprocessing"]["fitted_split"] == "train"
    assert report["preprocessing"]["encoded_feature_count"] == 42
    assert report["training_gate"]["synthetic_bootstrap_pipeline_ready"] is True
    assert report["training_gate"]["production_accuracy_training_ready"] is False

    for split, expected in (("train", 1680), ("validation", 360), ("test", 360)):
        rows = _read_csv(output / f"{split}.csv")
        assert len(rows) == expected
        assert len(rows[0]) == 47


def test_training_numeric_features_are_standardized_from_train_only(
    tmp_path: Path,
) -> None:
    output, _ = _prepare(tmp_path)
    rows = _read_csv(output / "train.csv")

    for field in NUMERIC_FEATURES:
        values = [float(row[f"num__{field}"]) for row in rows]
        assert statistics.fmean(values) == pytest.approx(0, abs=1e-10)
        assert statistics.pstdev(values) == pytest.approx(1, abs=1e-10)


def test_preparation_is_byte_deterministic(tmp_path: Path) -> None:
    first, _ = _prepare(tmp_path, "first")
    second, _ = _prepare(tmp_path, "second")

    for filename in (
        "train.csv",
        "validation.csv",
        "test.csv",
        "preprocessing.json",
        "preparation_report.json",
    ):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_unknown_category_uses_frozen_unknown_bucket() -> None:
    source_rows = _read_csv(
        DEFAULT_DATA_DIR / "training" / "recommendation_samples_v1.csv"
    )
    train_rows = [row for row in source_rows if row["dataset_split"] == "train"]
    preprocessor = DatasetPreprocessor().fit(train_rows)
    unseen = deepcopy(train_rows[0])
    unseen["event_type"] = "unseen_event"

    transformed = preprocessor.transform_row(unseen)

    assert transformed["cat__event_type__unknown"] == "1"
    assert sum(
        int(value)
        for key, value in transformed.items()
        if key.startswith("cat__event_type__")
    ) == 1


def test_preprocessor_refuses_to_fit_non_training_rows() -> None:
    source_rows = _read_csv(
        DEFAULT_DATA_DIR / "training" / "recommendation_samples_v1.csv"
    )
    validation_row = next(
        row for row in source_rows if row["dataset_split"] == "validation"
    )

    with pytest.raises(ValueError, match="only be fitted"):
        DatasetPreprocessor().fit([validation_row])


def test_preprocessing_metadata_contains_frozen_feature_order(tmp_path: Path) -> None:
    output, _ = _prepare(tmp_path)
    metadata = json.loads((output / "preprocessing.json").read_text(encoding="utf-8"))

    assert metadata["fitted_split"] == "train"
    assert metadata["fitted_row_count"] == 1680
    assert metadata["categorical_features"] == list(CATEGORICAL_FEATURES)
    assert len(metadata["feature_columns"]) == 42
    assert metadata["output_columns"][0] == "scenario_id"


def test_preparation_preserves_existing_human_review_values(tmp_path: Path) -> None:
    root = tmp_path / "preserve"
    output = root / "processed"
    review_path = root / "review.csv"
    review_status = root / "review_status.json"
    prepare_dataset(
        output_dir=output,
        review_path=review_path,
        review_status_path=review_status,
    )
    rows = _read_csv(review_path)
    rows[0]["expert_theme_label"] = rows[0]["current_theme_label"]
    rows[0]["expert_cake_label"] = rows[0]["current_cake_label"]
    rows[0]["expert_decor_label"] = rows[0]["current_decor_label"]
    rows[0]["expert_layout_label"] = rows[0]["current_layout_label"]
    rows[0]["expert_confidence"] = "5"
    rows[0]["expert_role"] = "baker"
    rows[0]["expert_id"] = "baker-01"
    rows[0]["review_decision"] = "approve"
    rows[0]["reviewed_at_utc"] = "2026-08-18T10:30:00Z"
    _write_csv(review_path, rows)

    prepare_dataset(
        output_dir=output,
        review_path=review_path,
        review_status_path=review_status,
    )

    preserved = _read_csv(review_path)
    assert preserved[0]["expert_id"] == "baker-01"
    assert preserved[0]["review_decision"] == "approve"
