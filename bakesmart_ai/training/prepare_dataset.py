"""Prepare leakage-safe, training-ready BakeSmart dataset splits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

from training.preprocessing import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_FIELDS,
    DatasetPreprocessor,
)
from training.review_dataset import EXPERT_FIELDS, audit_review_rows
from training.validate_datasets import DEFAULT_DATA_DIR, validate_data_directory


DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "processed" / "v1"
DEFAULT_REVIEW_PATH = DEFAULT_DATA_DIR / "review" / "expert_review_assignments_v1.csv"
DEFAULT_REVIEW_STATUS_PATH = DEFAULT_DATA_DIR / "review" / "review_status_v1.json"
SOURCE_PATH = "training/recommendation_samples_v1.csv"
SOURCE_REVIEW_PATH = "training/expert_review_template_v1.csv"
EXPECTED_SPLIT_COUNTS = {"train": 1680, "validation": 360, "test": 360}

BASE_NUMERIC_FEATURES = (
    "guest_count",
    "room_length_m",
    "room_width_m",
    "room_area_m2",
    "budget_pkr",
    "budget_per_guest_pkr",
)
SOURCE_FEATURE_FIELDS = (*BASE_NUMERIC_FEATURES, *CATEGORICAL_FEATURES)

REVIEW_ASSIGNMENT_HEADERS = [
    "assignment_id",
    "reviewer_slot",
    "scenario_id",
    "event_type",
    "venue_type",
    "guest_count",
    "room_length_m",
    "room_width_m",
    "budget_pkr",
    "age_group",
    "time_of_day",
    "preferred_color",
    "preferred_style",
    "current_theme_label",
    "current_cake_label",
    "current_decor_label",
    "current_layout_label",
    "expert_theme_label",
    "expert_cake_label",
    "expert_decor_label",
    "expert_layout_label",
    "expert_confidence",
    "expert_role",
    "expert_id",
    "review_decision",
    "comments",
    "reviewed_at_utc",
]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[Mapping[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_manifest_entry(data_dir: Path) -> dict[str, object]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["path"] == SOURCE_PATH:
            return entry
    raise ValueError(f"{SOURCE_PATH} is missing from data/manifest.json")


def _build_review_assignments(
    source_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    assignments: list[dict[str, str]] = []
    for source in source_rows:
        for slot in (1, 2):
            row = {header: source.get(header, "") for header in REVIEW_ASSIGNMENT_HEADERS}
            row["assignment_id"] = f"{source['scenario_id']}-R{slot}"
            row["reviewer_slot"] = str(slot)
            row["reviewed_at_utc"] = ""
            assignments.append(row)
    return assignments


def _review_skeleton(row: Mapping[str, str]) -> tuple[str, ...]:
    non_review_fields = [
        header
        for header in REVIEW_ASSIGNMENT_HEADERS
        if header not in {*EXPERT_FIELDS, "reviewed_at_utc"}
    ]
    return tuple(row.get(header, "") for header in non_review_fields)


def _load_or_create_review_assignments(
    source_review_rows: list[dict[str, str]],
    review_path: Path,
) -> list[dict[str, str]]:
    expected = _build_review_assignments(source_review_rows)
    if not review_path.exists():
        _write_csv(review_path, REVIEW_ASSIGNMENT_HEADERS, expected)
        return expected

    headers, existing = _read_csv(review_path)
    if headers != REVIEW_ASSIGNMENT_HEADERS:
        raise ValueError("existing review assignment schema does not match Phase 4")
    if [_review_skeleton(row) for row in existing] != [
        _review_skeleton(row) for row in expected
    ]:
        raise ValueError(
            "existing review assignments do not match the source scenarios; "
            "review data was preserved and requires an explicit migration"
        )
    return existing


def _audit_split_leakage(
    splits: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    scenario_sets = {
        split: {row["scenario_id"] for row in rows} for split, rows in splits.items()
    }
    feature_sets = {
        split: {tuple(row[field] for field in SOURCE_FEATURE_FIELDS) for row in rows}
        for split, rows in splits.items()
    }
    pair_names = (("train", "validation"), ("train", "test"), ("validation", "test"))
    scenario_overlap = {
        f"{first}_vs_{second}": len(scenario_sets[first] & scenario_sets[second])
        for first, second in pair_names
    }
    feature_overlap = {
        f"{first}_vs_{second}": len(feature_sets[first] & feature_sets[second])
        for first, second in pair_names
    }
    duplicate_features_within_split = {
        split: len(rows) - len(feature_sets[split]) for split, rows in splits.items()
    }
    passed = (
        not any(scenario_overlap.values())
        and not any(feature_overlap.values())
        and not any(duplicate_features_within_split.values())
    )
    if not passed:
        raise ValueError("dataset split leakage or duplicate feature signatures detected")
    return {
        "passed": True,
        "scenario_id_overlap": scenario_overlap,
        "feature_signature_overlap": feature_overlap,
        "duplicate_features_within_split": duplicate_features_within_split,
    }


def _unknown_category_counts(
    splits: dict[str, list[dict[str, str]]],
    preprocessor: DatasetPreprocessor,
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for split, rows in splits.items():
        counts[split] = {}
        for field in CATEGORICAL_FEATURES:
            known = set(preprocessor.categorical_vocabularies[field])
            counts[split][field] = sum(row[field] not in known for row in rows)
    return counts


def _validate_transformed_rows(
    split: str,
    rows: list[dict[str, str]],
    preprocessor: DatasetPreprocessor,
) -> None:
    if len(rows) != EXPECTED_SPLIT_COUNTS[split]:
        raise ValueError(f"processed {split} split has an unexpected row count")
    expected_columns = preprocessor.output_columns
    for row in rows:
        if list(row) != expected_columns:
            raise ValueError(f"processed {split} row has an unexpected schema")
        for field in NUMERIC_FEATURES:
            value = float(row[f"num__{field}"])
            if not math.isfinite(value):
                raise ValueError(f"processed {split} contains a non-finite value")
        for field in CATEGORICAL_FEATURES:
            columns = [
                column
                for column in preprocessor.feature_columns
                if column.startswith(f"cat__{field}__")
            ]
            if sum(int(row[column]) for column in columns) != 1:
                raise ValueError(f"processed {split} has invalid one-hot values")
        for source_target, output_target in TARGET_FIELDS.items():
            target_id = int(row[output_target])
            if target_id not in preprocessor.target_label_to_id[source_target].values():
                raise ValueError(f"processed {split} has an invalid target ID")


def prepare_dataset(
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    review_path: Path = DEFAULT_REVIEW_PATH,
    review_status_path: Path = DEFAULT_REVIEW_STATUS_PATH,
) -> dict[str, object]:
    """Validate, review-audit, preprocess, and write Phase 4 artifacts."""

    data_dir = data_dir.resolve()
    output_dir = output_dir.resolve()
    review_path = review_path.resolve()
    review_status_path = review_status_path.resolve()

    source_validation = validate_data_directory(data_dir)
    if not source_validation.valid:
        raise ValueError(f"Phase 3 validation failed: {source_validation.to_dict()}")

    _, rows = _read_csv(data_dir / SOURCE_PATH)
    _, source_review_rows = _read_csv(data_dir / SOURCE_REVIEW_PATH)
    review_rows = _load_or_create_review_assignments(source_review_rows, review_path)
    review_audit = audit_review_rows(review_rows)
    if not review_audit.valid:
        raise ValueError(f"expert review audit failed: {review_audit.to_dict()}")

    splits = {
        split: [row for row in rows if row["dataset_split"] == split]
        for split in EXPECTED_SPLIT_COUNTS
    }
    split_counts = {split: len(split_rows) for split, split_rows in splits.items()}
    if split_counts != EXPECTED_SPLIT_COUNTS:
        raise ValueError(f"locked split counts changed: {split_counts}")
    leakage_audit = _audit_split_leakage(splits)

    preprocessor = DatasetPreprocessor().fit(splits["train"])
    transformed = {
        split: preprocessor.transform(split_rows) for split, split_rows in splits.items()
    }
    for split, transformed_rows in transformed.items():
        _validate_transformed_rows(split, transformed_rows, preprocessor)

    split_paths: dict[str, Path] = {}
    for split, transformed_rows in transformed.items():
        path = output_dir / f"{split}.csv"
        _write_csv(path, preprocessor.output_columns, transformed_rows)
        split_paths[split] = path

    unknown_counts = _unknown_category_counts(splits, preprocessor)
    split_checksums = {
        split: _sha256(path) for split, path in sorted(split_paths.items())
    }
    source_entry = _source_manifest_entry(data_dir)
    preprocessing_document = {
        **preprocessor.to_dict(),
        "source_dataset": SOURCE_PATH,
        "source_sha256": source_entry["sha256"],
        "source_label_type": "synthetic_rule_based_silver",
        "source_review_status": "pending_expert_review",
        "split_counts": split_counts,
        "processed_split_sha256": split_checksums,
    }
    _write_json(output_dir / "preprocessing.json", preprocessing_document)

    real_world_test_path = data_dir / "training" / "real_world_test_v1.csv"
    review_status = {
        **review_audit.to_dict(),
        "required_reviews_per_scenario": 2,
        "required_review_scenarios": len(source_review_rows),
        "real_world_test_set_present": real_world_test_path.is_file(),
    }
    _write_json(review_status_path, review_status)

    gate_reasons: list[str] = []
    if not review_audit.complete:
        gate_reasons.append("independent expert review assignments are incomplete")
    if review_audit.scenarios_with_two_completed_reviews != len(source_review_rows):
        gate_reasons.append("two independent completed reviews are required per scenario")
    incomplete_agreement_labels = [
        label
        for label, values in review_audit.agreement.items()
        if values["paired_scenarios"] != len(source_review_rows)
    ]
    if incomplete_agreement_labels:
        gate_reasons.append(
            "paired expert labels are incomplete for: "
            + ", ".join(sorted(incomplete_agreement_labels))
        )
    if not real_world_test_path.is_file():
        gate_reasons.append("a locked, independently labelled real-world test set is absent")

    theme_counts = {
        split: dict(sorted(Counter(row["theme_label"] for row in split_rows).items()))
        for split, split_rows in splits.items()
    }
    report: dict[str, object] = {
        "phase": 4,
        "dataset_version": "1.0.0",
        "source_validation": {
            "valid": source_validation.valid,
            "files_checked": source_validation.files_checked,
            "records_checked": source_validation.records_checked,
            "checks_run": source_validation.checks_run,
        },
        "source": {
            "path": SOURCE_PATH,
            "records": len(rows),
            "sha256": source_entry["sha256"],
            "label_type": "synthetic_rule_based_silver",
        },
        "splits": split_counts,
        "theme_counts_by_split": theme_counts,
        "leakage_audit": leakage_audit,
        "preprocessing": {
            "fitted_split": "train",
            "fitted_rows": preprocessor.fitted_row_count,
            "numeric_feature_count": len(NUMERIC_FEATURES),
            "categorical_source_feature_count": len(CATEGORICAL_FEATURES),
            "encoded_feature_count": len(preprocessor.feature_columns),
            "target_count": len(TARGET_FIELDS),
            "unknown_category_counts": unknown_counts,
        },
        "review": review_status,
        "training_gate": {
            "synthetic_bootstrap_pipeline_ready": True,
            "production_accuracy_training_ready": not gate_reasons,
            "blocking_reasons": gate_reasons,
        },
        "outputs": {
            "split_sha256": split_checksums,
            "review_assignments_sha256": _sha256(review_path),
        },
    }
    _write_json(output_dir / "preparation_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-output", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument(
        "--review-status-output", type=Path, default=DEFAULT_REVIEW_STATUS_PATH
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = prepare_dataset(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            review_path=args.review_output,
            review_status_path=args.review_status_output,
        )
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "PASS: prepared 1,680 train, 360 validation, and 360 test rows; "
            "preprocessing fitted only on train"
        )
        print(
            "REVIEW: "
            f"{report['review']['completed_assignments']} completed and "
            f"{report['review']['pending_assignments']} pending assignments"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
