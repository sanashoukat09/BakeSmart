from __future__ import annotations

import csv
from copy import deepcopy

from training.prepare_dataset import _build_review_assignments
from training.review_dataset import audit_review_rows
from training.validate_datasets import DEFAULT_DATA_DIR


def _source_review_rows() -> list[dict[str, str]]:
    path = DEFAULT_DATA_DIR / "training" / "expert_review_template_v1.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _complete_approval(row: dict[str, str], expert_id: str, role: str) -> None:
    row["expert_theme_label"] = row["current_theme_label"]
    row["expert_cake_label"] = row["current_cake_label"]
    row["expert_decor_label"] = row["current_decor_label"]
    row["expert_layout_label"] = row["current_layout_label"]
    row["expert_confidence"] = "5"
    row["expert_role"] = role
    row["expert_id"] = expert_id
    row["review_decision"] = "approve"
    row["reviewed_at_utc"] = "2026-08-18T10:30:00Z"


def test_blank_review_assignments_are_pending_not_fabricated() -> None:
    rows = _build_review_assignments(_source_review_rows())

    audit = audit_review_rows(rows)

    assert audit.valid
    assert audit.total_assignments == 240
    assert audit.pending_assignments == 240
    assert audit.completed_assignments == 0
    assert not audit.complete


def test_two_independent_approvals_enable_paired_agreement() -> None:
    rows = _build_review_assignments(_source_review_rows())
    _complete_approval(rows[0], "baker-01", "baker")
    _complete_approval(rows[1], "decorator-01", "event_decorator")

    audit = audit_review_rows(rows)

    assert audit.valid
    assert audit.completed_assignments == 2
    assert audit.scenarios_with_two_completed_reviews == 1
    assert audit.agreement["theme_label"]["observed_agreement"] == 1


def test_same_expert_cannot_fill_both_reviewer_slots() -> None:
    rows = _build_review_assignments(_source_review_rows())
    _complete_approval(rows[0], "expert-01", "baker")
    _complete_approval(rows[1], "expert-01", "event_decorator")

    audit = audit_review_rows(rows)

    assert not audit.valid
    assert "independence" in {issue.code for issue in audit.issues}


def test_partial_review_is_invalid() -> None:
    rows = _build_review_assignments(_source_review_rows())
    rows[0]["expert_confidence"] = "5"

    audit = audit_review_rows(rows)

    assert not audit.valid
    assert audit.invalid_assignments == 1


def test_correct_decision_requires_a_changed_label_and_comments() -> None:
    rows = _build_review_assignments(_source_review_rows())
    candidate = deepcopy(rows[0])
    _complete_approval(candidate, "baker-01", "baker")
    candidate["review_decision"] = "correct"
    rows[0] = candidate

    audit = audit_review_rows(rows)

    codes = {issue.code for issue in audit.issues}
    assert "correction_missing" in codes
    assert "comments" in codes


def test_review_timestamp_must_include_iso_timezone() -> None:
    rows = _build_review_assignments(_source_review_rows())
    _complete_approval(rows[0], "baker-01", "baker")
    rows[0]["reviewed_at_utc"] = "18 August 2026"

    audit = audit_review_rows(rows)

    assert not audit.valid
    assert "reviewed_at" in {issue.code for issue in audit.issues}
