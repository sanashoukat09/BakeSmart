from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from training.validate_datasets import DEFAULT_DATA_DIR, validate_data_directory


def test_phase3_dataset_passes_all_checks() -> None:
    report = validate_data_directory()

    assert report.valid, report.to_dict()
    assert report.files_checked == 10
    assert report.records_checked == 2862
    assert report.checks_run > 50_000


def test_manifest_preserves_synthetic_label_status() -> None:
    manifest = json.loads((DEFAULT_DATA_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["label_type"] == "synthetic_rule_based_silver"
    assert manifest["review_status"] == "pending_expert_review"
    assert manifest["training_approved"] is False
    assert sum(file["records"] for file in manifest["files"]) == 2862


def test_validator_rejects_a_synthetic_row_marked_as_reviewed(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    shutil.copytree(DEFAULT_DATA_DIR, data_dir)
    samples_path = data_dir / "training" / "recommendation_samples_v1.csv"

    with samples_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    rows[0]["review_status"] = "expert_approved"
    with samples_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    report = validate_data_directory(data_dir, verify_checksums=False)

    assert not report.valid
    assert "row_review_status" in {issue.code for issue in report.issues}
