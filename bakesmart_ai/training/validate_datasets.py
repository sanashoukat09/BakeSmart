"""Validate the versioned BakeSmart Phase 3 datasets.

The validator intentionally uses only the Python standard library so dataset
integrity can be checked before any machine-learning dependencies are installed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MAX_REPORTED_ISSUES = 200

EXPECTED_FILES: dict[str, dict[str, object]] = {
    "catalogs/themes.csv": {
        "records": 26,
        "id": "theme_id",
        "headers": [
            "theme_id",
            "name",
            "event_types",
            "keywords",
            "visual_cues",
            "palette_hex",
            "materials",
            "mood",
            "best_space_fit",
            "lighting",
            "decor_summary",
            "cake_summary",
            "avoid",
        ],
    },
    "catalogs/decorations.csv": {
        "records": 130,
        "id": "decor_id",
        "headers": [
            "decor_id",
            "theme_id",
            "event_types",
            "category",
            "item_name",
            "description",
            "indoor_outdoor",
            "space_requirement",
            "placement_zone",
            "quantity_rule",
            "color_options",
            "material",
            "rental_or_purchase",
            "safety_notes",
            "ar_asset_key",
            "search_terms",
        ],
    },
    "catalogs/cake_designs.csv": {
        "records": 78,
        "id": "cake_design_id",
        "headers": [
            "cake_design_id",
            "theme_id",
            "event_types",
            "style_name",
            "shape",
            "suggested_tiers",
            "frosting_or_covering",
            "palette_hex",
            "design_elements",
            "topper_guidance",
            "finish",
            "serving_range",
            "price_tier",
            "allergen_notes",
            "structural_notes",
            "ar_asset_key",
        ],
    },
    "catalogs/cake_size_rules.csv": {
        "records": 12,
        "id": "rule_id",
        "headers": [
            "rule_id",
            "guest_min",
            "guest_max",
            "recommended_configuration",
            "tiers",
            "servings_min",
            "servings_max",
            "best_for",
            "portion_assumption",
            "buffer_rule",
            "validation_required",
        ],
    },
    "catalogs/event_profiles.csv": {
        "records": 12,
        "id": "event_type_id",
        "headers": [
            "event_type_id",
            "name",
            "audience",
            "core_zones",
            "design_priorities",
            "cake_portion_rule",
            "safety_and_cultural_notes",
        ],
    },
    "catalogs/placement_rules.csv": {
        "records": 12,
        "id": "rule_id",
        "headers": [
            "rule_id",
            "space_type",
            "event_types",
            "photo_cues",
            "recommended_placement",
            "min_walkway_cm",
            "backdrop_clearance_cm",
            "traffic_rule",
            "lighting_rule",
            "confidence_blockers",
        ],
    },
    "catalogs/ar_assets.csv": {
        "records": 52,
        "id": "asset_id",
        "headers": [
            "asset_id",
            "related_id",
            "asset_type",
            "glb_file",
            "usdz_file",
            "units",
            "default_dimensions_cm",
            "polygon_budget",
            "texture_guideline",
            "anchor_type",
            "interaction",
            "license_requirement",
            "production_status",
            "fallback",
        ],
    },
    "training/evaluation_cases.csv": {
        "records": 20,
        "id": "case_id",
        "headers": [
            "case_id",
            "event_type",
            "guest_count",
            "input_summary",
            "target_theme",
            "expected_behavior",
        ],
    },
    "training/recommendation_samples_v1.csv": {
        "records": 2400,
        "id": "scenario_id",
        "headers": [
            "scenario_id",
            "event_type",
            "venue_type",
            "guest_count",
            "room_length_m",
            "room_width_m",
            "room_area_m2",
            "budget_pkr",
            "budget_per_guest_pkr",
            "age_group",
            "time_of_day",
            "preferred_color",
            "preferred_style",
            "theme_label",
            "cake_label",
            "decor_label",
            "layout_label",
            "recommended_servings",
            "labelled_by",
            "confidence",
            "source",
            "review_status",
            "dataset_split",
            "generation_seed",
            "rule_notes",
        ],
    },
    "training/expert_review_template_v1.csv": {
        "records": 120,
        "id": "scenario_id",
        "headers": [
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
        ],
        "optional": [
            "expert_theme_label",
            "expert_cake_label",
            "expert_decor_label",
            "expert_layout_label",
            "expert_confidence",
            "expert_role",
            "expert_id",
            "review_decision",
            "comments",
        ],
    },
}

ALLOWED_RECOMMENDATION_VALUES = {
    "event_type": {
        "birthday",
        "wedding",
        "anniversary",
        "baby_shower",
        "graduation",
    },
    "venue_type": {"home", "hall", "outdoor", "restaurant"},
    "age_group": {"child", "teenager", "adult", "mixed"},
    "time_of_day": {"day", "night"},
    "preferred_color": {
        "pink",
        "blue",
        "white",
        "gold",
        "red",
        "purple",
        "green",
        "mixed",
    },
    "preferred_style": {
        "minimal",
        "elegant",
        "colourful",
        "rustic",
        "traditional",
    },
    "theme_label": {
        "pastel_floral",
        "modern_minimal",
        "elegant_gold",
        "rustic_natural",
        "colourful_cartoon",
        "traditional_luxury",
    },
    "cake_label": {
        "single_tier_round",
        "single_tier_square",
        "two_tier_round",
        "two_tier_floral",
        "three_tier_luxury",
    },
    "decor_label": {
        "balloon_setup",
        "flower_wall",
        "minimal_backdrop",
        "rustic_wood_setup",
        "luxury_stage",
    },
    "layout_label": {
        "single_cake_table",
        "cake_and_dessert_table",
        "two_side_tables",
        "full_stage_setup",
    },
    "dataset_split": {"train", "validation", "test"},
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


@dataclass
class ValidationReport:
    data_dir: str
    files_checked: int = 0
    records_checked: int = 0
    checks_run: int = 0
    issues: list[ValidationIssue] | None = None

    def __post_init__(self) -> None:
        if self.issues is None:
            self.issues = []

    @property
    def valid(self) -> bool:
        return not self.issues

    def check(self, condition: bool, code: str, path: str, message: str) -> None:
        self.checks_run += 1
        if condition or len(self.issues) >= MAX_REPORTED_ISSUES:
            return
        self.issues.append(ValidationIssue(code=code, path=path, message=message))

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "data_dir": self.data_dir,
            "files_checked": self.files_checked,
            "records_checked": self.records_checked,
            "checks_run": self.checks_run,
            "issues": [asdict(issue) for issue in self.issues],
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _parse_decimal(
    row: dict[str, str],
    field: str,
    row_path: str,
    report: ValidationReport,
) -> Decimal | None:
    try:
        return Decimal(row[field])
    except (InvalidOperation, KeyError):
        report.check(False, "invalid_number", row_path, f"{field} must be numeric")
        return None


def _parse_int(
    row: dict[str, str],
    field: str,
    row_path: str,
    report: ValidationReport,
) -> int | None:
    try:
        return int(row[field])
    except (TypeError, ValueError, KeyError):
        report.check(False, "invalid_integer", row_path, f"{field} must be an integer")
        return None


def _validate_manifest(
    data_dir: Path,
    report: ValidationReport,
    verify_checksums: bool,
) -> dict[str, object]:
    manifest_path = data_dir / "manifest.json"
    report.check(manifest_path.is_file(), "missing_manifest", "manifest.json", "manifest is required")
    if not manifest_path.is_file():
        return {}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.check(False, "invalid_manifest", "manifest.json", str(exc))
        return {}

    report.check(
        manifest.get("label_type") == "synthetic_rule_based_silver",
        "label_disclosure",
        "manifest.json",
        "label_type must disclose synthetic silver labels",
    )
    report.check(
        manifest.get("review_status") == "pending_expert_review",
        "review_status",
        "manifest.json",
        "dataset must remain pending expert review",
    )
    report.check(
        manifest.get("training_approved") is False,
        "training_approval",
        "manifest.json",
        "Phase 3 data must not be marked training-approved",
    )

    entries = {entry.get("path"): entry for entry in manifest.get("files", [])}
    report.check(
        set(entries) == set(EXPECTED_FILES),
        "manifest_file_set",
        "manifest.json",
        "manifest file list does not match the Phase 3 dataset contract",
    )

    for relative_path, specification in EXPECTED_FILES.items():
        entry = entries.get(relative_path, {})
        report.check(
            entry.get("records") == specification["records"],
            "manifest_record_count",
            relative_path,
            "manifest record count does not match the dataset contract",
        )
        file_path = data_dir / relative_path
        report.check(file_path.is_file(), "missing_file", relative_path, "dataset file is missing")
        if verify_checksums and file_path.is_file():
            report.check(
                _sha256(file_path) == entry.get("sha256"),
                "checksum_mismatch",
                relative_path,
                "SHA-256 does not match manifest",
            )
    return manifest


def _load_and_validate_files(
    data_dir: Path,
    report: ValidationReport,
) -> dict[str, list[dict[str, str]]]:
    loaded: dict[str, list[dict[str, str]]] = {}
    for relative_path, specification in EXPECTED_FILES.items():
        file_path = data_dir / relative_path
        if not file_path.is_file():
            continue
        headers, rows = _read_csv(file_path)
        report.files_checked += 1
        report.records_checked += len(rows)
        loaded[relative_path] = rows

        expected_headers = specification["headers"]
        report.check(
            headers == expected_headers,
            "schema_mismatch",
            relative_path,
            f"expected headers {expected_headers}, got {headers}",
        )
        report.check(
            len(rows) == specification["records"],
            "record_count",
            relative_path,
            f"expected {specification['records']} records, got {len(rows)}",
        )

        optional = set(specification.get("optional", []))
        required = [header for header in expected_headers if header not in optional]
        identifier = str(specification["id"])
        identifiers: list[str] = []
        for index, row in enumerate(rows, start=2):
            row_path = f"{relative_path}:{index}"
            for field in required:
                report.check(
                    bool(row.get(field, "").strip()),
                    "missing_required_value",
                    row_path,
                    f"{field} is required",
                )
            identifiers.append(row.get(identifier, ""))
        report.check(
            len(identifiers) == len(set(identifiers)),
            "duplicate_identifier",
            relative_path,
            f"{identifier} values must be unique",
        )
    return loaded


def _validate_catalogues(
    loaded: dict[str, list[dict[str, str]]],
    report: ValidationReport,
) -> None:
    themes = loaded.get("catalogs/themes.csv", [])
    decorations = loaded.get("catalogs/decorations.csv", [])
    cakes = loaded.get("catalogs/cake_designs.csv", [])
    size_rules = loaded.get("catalogs/cake_size_rules.csv", [])
    placements = loaded.get("catalogs/placement_rules.csv", [])
    assets = loaded.get("catalogs/ar_assets.csv", [])
    evaluation_cases = loaded.get("training/evaluation_cases.csv", [])

    theme_ids = {row["theme_id"] for row in themes}
    theme_names = {row["name"].lower().replace("&", "and") for row in themes}
    hex_color = re.compile(r"#[0-9A-Fa-f]{6}")

    for row in themes:
        colors = row["palette_hex"].split(";")
        report.check(
            bool(colors) and all(hex_color.fullmatch(color) for color in colors),
            "invalid_palette",
            f"catalogs/themes.csv:{row['theme_id']}",
            "palette_hex must contain semicolon-separated #RRGGBB values",
        )

    for relative_path, rows in (
        ("catalogs/decorations.csv", decorations),
        ("catalogs/cake_designs.csv", cakes),
    ):
        for row in rows:
            report.check(
                row["theme_id"] in theme_ids,
                "unknown_theme",
                f"{relative_path}:{row.get('theme_id', '')}",
                "theme_id does not exist in themes.csv",
            )

    decoration_counts = Counter(row["theme_id"] for row in decorations)
    cake_counts = Counter(row["theme_id"] for row in cakes)
    asset_counts = Counter(row["related_id"] for row in assets)
    for theme_id in theme_ids:
        report.check(
            decoration_counts[theme_id] == 5,
            "theme_decoration_count",
            f"catalogs/decorations.csv:{theme_id}",
            "each theme must have exactly five decoration records",
        )
        report.check(
            cake_counts[theme_id] == 3,
            "theme_cake_count",
            f"catalogs/cake_designs.csv:{theme_id}",
            "each theme must have exactly three cake records",
        )
        report.check(
            asset_counts[theme_id] == 2,
            "theme_asset_count",
            f"catalogs/ar_assets.csv:{theme_id}",
            "each theme must have one scene bundle and one cake variant set",
        )

    for row in cakes:
        match = re.fullmatch(r"(\d+)-(\d+)", row["serving_range"])
        report.check(
            bool(match) and int(match.group(1)) <= int(match.group(2)),
            "invalid_serving_range",
            f"catalogs/cake_designs.csv:{row['cake_design_id']}",
            "serving_range must be an ascending min-max pair",
        )

    for row in size_rules:
        row_path = f"catalogs/cake_size_rules.csv:{row['rule_id']}"
        values = {
            field: _parse_int(row, field, row_path, report)
            for field in ("guest_min", "guest_max", "tiers", "servings_min", "servings_max")
        }
        if all(value is not None for value in values.values()):
            report.check(
                values["guest_min"] > 0 and values["guest_min"] <= values["guest_max"],
                "invalid_guest_range",
                row_path,
                "guest range must be positive and ascending",
            )
            report.check(
                values["servings_min"] > 0
                and values["servings_min"] <= values["servings_max"],
                "invalid_servings_range",
                row_path,
                "servings range must be positive and ascending",
            )
            report.check(
                values["tiers"] > 0,
                "invalid_tier_count",
                row_path,
                "tiers must be positive",
            )

    for row in placements:
        row_path = f"catalogs/placement_rules.csv:{row['rule_id']}"
        for field in ("min_walkway_cm", "backdrop_clearance_cm"):
            value = _parse_int(row, field, row_path, report)
            if value is not None:
                report.check(
                    value > 0,
                    "invalid_clearance",
                    row_path,
                    f"{field} must be positive",
                )

    for row in assets:
        row_path = f"catalogs/ar_assets.csv:{row['asset_id']}"
        report.check(
            row["related_id"] in theme_ids,
            "unknown_asset_theme",
            row_path,
            "related_id does not exist in themes.csv",
        )
        report.check(
            row["glb_file"].endswith(".glb") and row["usdz_file"].endswith(".usdz"),
            "invalid_asset_path",
            row_path,
            "AR asset paths must use .glb and .usdz extensions",
        )

    for row in evaluation_cases:
        row_path = f"training/evaluation_cases.csv:{row['case_id']}"
        guest_count = _parse_int(row, "guest_count", row_path, report)
        if guest_count is not None:
            report.check(
                guest_count > 0,
                "invalid_guest_count",
                row_path,
                "guest_count must be positive",
            )
        report.check(
            row["target_theme"].lower().replace("&", "and") in theme_names,
            "unknown_evaluation_theme",
            row_path,
            "target_theme does not match a catalogue theme name",
        )


def _validate_recommendations(
    rows: list[dict[str, str]],
    report: ValidationReport,
) -> None:
    theme_counts: Counter[str] = Counter()
    cake_counts: Counter[str] = Counter()
    decor_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    theme_split_counts: Counter[tuple[str, str]] = Counter()
    signatures: set[tuple[str, ...]] = set()
    headers = EXPECTED_FILES["training/recommendation_samples_v1.csv"]["headers"]

    for row_number, row in enumerate(rows, start=2):
        row_path = f"training/recommendation_samples_v1.csv:{row_number}"
        report.check(
            bool(re.fullmatch(r"BSAR\d{4}", row["scenario_id"])),
            "invalid_scenario_id",
            row_path,
            "scenario_id must match BSAR0001 format",
        )
        for field, allowed in ALLOWED_RECOMMENDATION_VALUES.items():
            report.check(
                row[field] in allowed,
                "unknown_category",
                row_path,
                f"{field} has unsupported value {row[field]!r}",
            )

        guest_count = _parse_int(row, "guest_count", row_path, report)
        length = _parse_decimal(row, "room_length_m", row_path, report)
        width = _parse_decimal(row, "room_width_m", row_path, report)
        area = _parse_decimal(row, "room_area_m2", row_path, report)
        budget = _parse_int(row, "budget_pkr", row_path, report)
        budget_per_guest = _parse_int(row, "budget_per_guest_pkr", row_path, report)
        servings = _parse_int(row, "recommended_servings", row_path, report)
        confidence = _parse_int(row, "confidence", row_path, report)
        seed = _parse_int(row, "generation_seed", row_path, report)

        if guest_count is not None:
            report.check(
                8 <= guest_count <= 250,
                "guest_count_range",
                row_path,
                "guest_count must be between 8 and 250 for dataset v1",
            )
        if length is not None and width is not None and area is not None:
            expected_area = (length * width).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            report.check(
                abs(area - expected_area) <= Decimal("0.1"),
                "area_derivation",
                row_path,
                "room_area_m2 must be within 0.1 m² of rounded length × width "
                f"({expected_area}); source dimensions are stored to one decimal place",
            )
        if guest_count and budget is not None and budget_per_guest is not None:
            expected_budget_per_guest = int(
                (Decimal(budget) / Decimal(guest_count)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            report.check(
                budget > 0,
                "budget_range",
                row_path,
                "budget_pkr must be positive",
            )
            report.check(
                budget_per_guest == expected_budget_per_guest,
                "budget_derivation",
                row_path,
                "budget_per_guest_pkr must equal rounded budget ÷ guests",
            )
        if guest_count is not None and servings is not None:
            report.check(
                servings == guest_count,
                "servings_derivation",
                row_path,
                "recommended_servings must equal guest_count in dataset v1",
            )
        if confidence is not None:
            report.check(
                3 <= confidence <= 5,
                "confidence_range",
                row_path,
                "confidence must be between 3 and 5",
            )
        report.check(
            seed == 20260817,
            "generation_seed",
            row_path,
            "generation_seed must remain locked at 20260817",
        )
        report.check(
            row["labelled_by"] == "bakesmart_rule_generator_v1",
            "label_source",
            row_path,
            "labelled_by must not imply human labelling",
        )
        report.check(
            row["source"] == "synthetic_rule_based",
            "source_disclosure",
            row_path,
            "source must disclose rule-based synthetic generation",
        )
        report.check(
            row["review_status"] == "pending_expert_review",
            "row_review_status",
            row_path,
            "synthetic labels must remain pending expert review",
        )

        theme = row["theme_label"]
        split = row["dataset_split"]
        theme_counts[theme] += 1
        cake_counts[row["cake_label"]] += 1
        decor_counts[row["decor_label"]] += 1
        split_counts[split] += 1
        theme_split_counts[(theme, split)] += 1
        signature = tuple(row[field] for field in headers if field != "scenario_id")
        report.check(
            signature not in signatures,
            "duplicate_signature",
            row_path,
            "feature/label signature is duplicated",
        )
        signatures.add(signature)

    report.check(
        split_counts == Counter({"train": 1680, "validation": 360, "test": 360}),
        "split_balance",
        "training/recommendation_samples_v1.csv",
        f"expected 1680/360/360 split, got {dict(split_counts)}",
    )
    for theme in ALLOWED_RECOMMENDATION_VALUES["theme_label"]:
        report.check(
            theme_counts[theme] == 400,
            "theme_balance",
            "training/recommendation_samples_v1.csv",
            f"theme {theme} must have 400 records",
        )
        for split, expected in (("train", 280), ("validation", 60), ("test", 60)):
            report.check(
                theme_split_counts[(theme, split)] == expected,
                "stratified_split",
                "training/recommendation_samples_v1.csv",
                f"theme {theme} must have {expected} {split} records",
            )
    for label in ALLOWED_RECOMMENDATION_VALUES["cake_label"]:
        report.check(
            cake_counts[label] == 480,
            "cake_balance",
            "training/recommendation_samples_v1.csv",
            f"cake label {label} must have 480 records",
        )
    for label in ALLOWED_RECOMMENDATION_VALUES["decor_label"]:
        report.check(
            decor_counts[label] == 480,
            "decor_balance",
            "training/recommendation_samples_v1.csv",
            f"decor label {label} must have 480 records",
        )


def _validate_expert_template(
    review_rows: list[dict[str, str]],
    recommendation_rows: list[dict[str, str]],
    report: ValidationReport,
) -> None:
    recommendations = {row["scenario_id"]: row for row in recommendation_rows}
    expert_fields = set(
        EXPECTED_FILES["training/expert_review_template_v1.csv"].get("optional", [])
    )
    source_mapping = {
        "event_type": "event_type",
        "venue_type": "venue_type",
        "guest_count": "guest_count",
        "room_length_m": "room_length_m",
        "room_width_m": "room_width_m",
        "budget_pkr": "budget_pkr",
        "age_group": "age_group",
        "time_of_day": "time_of_day",
        "preferred_color": "preferred_color",
        "preferred_style": "preferred_style",
        "current_theme_label": "theme_label",
        "current_cake_label": "cake_label",
        "current_decor_label": "decor_label",
        "current_layout_label": "layout_label",
    }
    theme_counts: Counter[str] = Counter()

    for row_number, row in enumerate(review_rows, start=2):
        row_path = f"training/expert_review_template_v1.csv:{row_number}"
        source = recommendations.get(row["scenario_id"])
        report.check(
            source is not None,
            "unknown_review_scenario",
            row_path,
            "expert-review scenario is absent from recommendation data",
        )
        if source is not None:
            for review_field, source_field in source_mapping.items():
                report.check(
                    row[review_field] == source[source_field],
                    "review_source_mismatch",
                    row_path,
                    f"{review_field} does not match source scenario",
                )
        for field in expert_fields:
            report.check(
                row[field] == "",
                "review_field_not_blank",
                row_path,
                f"{field} must be blank before independent expert review",
            )
        theme_counts[row["current_theme_label"]] += 1

    for theme in ALLOWED_RECOMMENDATION_VALUES["theme_label"]:
        report.check(
            theme_counts[theme] == 20,
            "review_theme_balance",
            "training/expert_review_template_v1.csv",
            f"expert template must contain 20 rows for theme {theme}",
        )


def validate_data_directory(
    data_dir: Path = DEFAULT_DATA_DIR,
    *,
    verify_checksums: bool = True,
) -> ValidationReport:
    """Run all Phase 3 integrity and semantic checks."""

    data_dir = data_dir.resolve()
    report = ValidationReport(data_dir=str(data_dir))
    _validate_manifest(data_dir, report, verify_checksums)
    loaded = _load_and_validate_files(data_dir, report)
    _validate_catalogues(loaded, report)

    recommendations = loaded.get("training/recommendation_samples_v1.csv", [])
    reviews = loaded.get("training/expert_review_template_v1.csv", [])
    if recommendations:
        _validate_recommendations(recommendations, report)
    if reviews and recommendations:
        _validate_expert_template(reviews, recommendations, report)
    return report


def _format_issues(issues: Iterable[ValidationIssue]) -> str:
    return "\n".join(
        f"- [{issue.code}] {issue.path}: {issue.message}" for issue in issues
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Path to the BakeSmart data directory",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    args = parser.parse_args()

    report = validate_data_directory(args.data_dir)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif report.valid:
        print(
            "PASS: "
            f"{report.files_checked} files, {report.records_checked} records, "
            f"{report.checks_run} checks"
        )
    else:
        print(
            "FAIL: "
            f"{len(report.issues)} issue(s) after {report.checks_run} checks\n"
            f"{_format_issues(report.issues)}"
        )
    return 0 if report.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
