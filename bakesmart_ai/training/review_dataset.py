"""Audit BakeSmart's independent human-review assignment file."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from training.validate_datasets import ALLOWED_RECOMMENDATION_VALUES


DEFAULT_REVIEW_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "review"
    / "expert_review_assignments_v1.csv"
)

CURRENT_LABEL_FIELDS = {
    "current_theme_label": "theme_label",
    "current_cake_label": "cake_label",
    "current_decor_label": "decor_label",
    "current_layout_label": "layout_label",
}
EXPERT_LABEL_FIELDS = {
    "expert_theme_label": "theme_label",
    "expert_cake_label": "cake_label",
    "expert_decor_label": "decor_label",
    "expert_layout_label": "layout_label",
}
EXPERT_FIELDS = (
    *EXPERT_LABEL_FIELDS,
    "expert_confidence",
    "expert_role",
    "expert_id",
    "review_decision",
    "comments",
    "reviewed_at_utc",
)
ALLOWED_ROLES = {"baker", "event_decorator", "baker_and_event_decorator"}
ALLOWED_DECISIONS = {"approve", "correct", "reject"}


@dataclass(frozen=True)
class ReviewIssue:
    assignment_id: str
    code: str
    message: str


@dataclass
class ReviewAudit:
    total_assignments: int = 0
    completed_assignments: int = 0
    pending_assignments: int = 0
    invalid_assignments: int = 0
    scenarios_with_two_completed_reviews: int = 0
    completed_by_role: dict[str, int] = field(default_factory=dict)
    agreement: dict[str, dict[str, float | int | None]] = field(default_factory=dict)
    issues: list[ReviewIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def complete(self) -> bool:
        return self.valid and self.pending_assignments == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "complete": self.complete,
            "total_assignments": self.total_assignments,
            "completed_assignments": self.completed_assignments,
            "pending_assignments": self.pending_assignments,
            "invalid_assignments": self.invalid_assignments,
            "scenarios_with_two_completed_reviews": (
                self.scenarios_with_two_completed_reviews
            ),
            "completed_by_role": self.completed_by_role,
            "agreement": self.agreement,
            "issues": [asdict(issue) for issue in self.issues],
        }


def _cohen_kappa(pairs: list[tuple[str, str]]) -> dict[str, float | int | None]:
    if not pairs:
        return {"paired_scenarios": 0, "observed_agreement": None, "kappa": None}
    observed = sum(first == second for first, second in pairs) / len(pairs)
    first_counts = Counter(first for first, _ in pairs)
    second_counts = Counter(second for _, second in pairs)
    categories = set(first_counts) | set(second_counts)
    expected = sum(
        (first_counts[value] / len(pairs)) * (second_counts[value] / len(pairs))
        for value in categories
    )
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    return {
        "paired_scenarios": len(pairs),
        "observed_agreement": observed,
        "kappa": kappa,
    }


def audit_review_rows(rows: list[dict[str, str]]) -> ReviewAudit:
    audit = ReviewAudit(total_assignments=len(rows))
    completed_by_role: Counter[str] = Counter()
    completed_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    assignments_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    assignment_ids: set[str] = set()

    for row in rows:
        assignment_id = row.get("assignment_id", "")
        scenario_id = row.get("scenario_id", "")
        reviewer_slot = row.get("reviewer_slot", "")
        assignments_by_scenario[scenario_id].append(row)
        if not assignment_id or assignment_id in assignment_ids:
            audit.issues.append(
                ReviewIssue(assignment_id, "assignment_id", "assignment_id must be unique")
            )
        assignment_ids.add(assignment_id)
        if assignment_id != f"{scenario_id}-R{reviewer_slot}":
            audit.issues.append(
                ReviewIssue(
                    assignment_id,
                    "assignment_mapping",
                    "assignment_id must match scenario_id and reviewer_slot",
                )
            )

        expert_values = [row.get(field, "").strip() for field in EXPERT_FIELDS]
        if not any(expert_values):
            audit.pending_assignments += 1
            continue

        row_issues: list[ReviewIssue] = []
        decision = row.get("review_decision", "").strip()
        role = row.get("expert_role", "").strip()
        expert_id = row.get("expert_id", "").strip()
        confidence = row.get("expert_confidence", "").strip()
        reviewed_at = row.get("reviewed_at_utc", "").strip()

        if decision not in ALLOWED_DECISIONS:
            row_issues.append(
                ReviewIssue(assignment_id, "decision", "unsupported review_decision")
            )
        if role not in ALLOWED_ROLES:
            row_issues.append(
                ReviewIssue(assignment_id, "role", "unsupported expert_role")
            )
        if not expert_id:
            row_issues.append(
                ReviewIssue(assignment_id, "expert_id", "expert_id is required")
            )
        try:
            confidence_value = int(confidence)
        except ValueError:
            confidence_value = 0
        if not 1 <= confidence_value <= 5:
            row_issues.append(
                ReviewIssue(assignment_id, "confidence", "confidence must be 1-5")
            )
        if not reviewed_at:
            row_issues.append(
                ReviewIssue(assignment_id, "reviewed_at", "reviewed_at_utc is required")
            )
        else:
            try:
                parsed_reviewed_at = datetime.fromisoformat(
                    reviewed_at.replace("Z", "+00:00")
                )
                if parsed_reviewed_at.tzinfo is None:
                    raise ValueError("timezone is required")
            except ValueError:
                row_issues.append(
                    ReviewIssue(
                        assignment_id,
                        "reviewed_at",
                        "reviewed_at_utc must be a timezone-aware ISO 8601 value",
                    )
                )

        expert_labels: dict[str, str] = {}
        for expert_field, label_field in EXPERT_LABEL_FIELDS.items():
            value = row.get(expert_field, "").strip()
            expert_labels[label_field] = value
            if decision in {"approve", "correct"} and value not in ALLOWED_RECOMMENDATION_VALUES[label_field]:
                row_issues.append(
                    ReviewIssue(
                        assignment_id,
                        "label",
                        f"{expert_field} is required and must be an allowed label",
                    )
                )

        current_labels = {
            label_field: row.get(current_field, "").strip()
            for current_field, label_field in CURRENT_LABEL_FIELDS.items()
        }
        if decision == "approve" and expert_labels != current_labels:
            row_issues.append(
                ReviewIssue(
                    assignment_id,
                    "approve_mismatch",
                    "approve requires expert labels to equal current labels",
                )
            )
        if decision == "correct" and expert_labels == current_labels:
            row_issues.append(
                ReviewIssue(
                    assignment_id,
                    "correction_missing",
                    "correct requires at least one changed label",
                )
            )
        if decision in {"correct", "reject"} and not row.get("comments", "").strip():
            row_issues.append(
                ReviewIssue(
                    assignment_id,
                    "comments",
                    "comments are required for corrected or rejected assignments",
                )
            )

        if row_issues:
            audit.invalid_assignments += 1
            audit.issues.extend(row_issues)
            continue

        audit.completed_assignments += 1
        completed_by_role[role] += 1
        completed_by_scenario[scenario_id].append(row)

    for scenario_id, assignments in assignments_by_scenario.items():
        slots = sorted(row.get("reviewer_slot", "") for row in assignments)
        if slots != ["1", "2"]:
            audit.issues.append(
                ReviewIssue(
                    scenario_id,
                    "reviewer_slots",
                    "every scenario must have exactly reviewer slots 1 and 2",
                )
            )

    paired: dict[str, list[tuple[str, str]]] = {
        label: [] for label in EXPERT_LABEL_FIELDS.values()
    }
    for reviews in completed_by_scenario.values():
        if len(reviews) != 2:
            continue
        reviews = sorted(reviews, key=lambda row: row["reviewer_slot"])
        if reviews[0]["expert_id"] == reviews[1]["expert_id"]:
            audit.issues.append(
                ReviewIssue(
                    reviews[0]["scenario_id"],
                    "independence",
                    "reviewer slots must be completed by different expert IDs",
                )
            )
            continue
        audit.scenarios_with_two_completed_reviews += 1
        for expert_field, label_field in EXPERT_LABEL_FIELDS.items():
            first = reviews[0].get(expert_field, "")
            second = reviews[1].get(expert_field, "")
            if first and second:
                paired[label_field].append((first, second))

    audit.completed_by_role = dict(sorted(completed_by_role.items()))
    audit.agreement = {
        label_field: _cohen_kappa(pairs) for label_field, pairs in paired.items()
    }
    return audit


def read_review_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    audit = audit_review_rows(read_review_rows(args.input))
    if args.json:
        print(json.dumps(audit.to_dict(), indent=2))
    else:
        print(
            f"Review assignments: {audit.completed_assignments} completed, "
            f"{audit.pending_assignments} pending, {audit.invalid_assignments} invalid"
        )
        if not audit.valid:
            for issue in audit.issues:
                print(f"- [{issue.code}] {issue.assignment_id}: {issue.message}")
    if not audit.valid:
        return 1
    if args.require_complete and not audit.complete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
