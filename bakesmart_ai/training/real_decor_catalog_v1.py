"""Validate Stage 2 data and collect only rights-safe Commons references."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.services.real_decor_catalog import DEFAULT_REAL_DECOR_DIR


CATALOG_FILES = (
    "decor_items.csv",
    "market_sources.csv",
    "photo_candidates.csv",
    "safety_profiles.csv",
    "authoritative_sources.csv",
)
CATEGORIES = {
    "backdrop",
    "floor-arrangement",
    "lighting",
    "table-setting",
    "signage",
}
PACKAGE_TIERS = {"essential", "balanced", "statement"}
ALLOWED_LICENSES = {
    "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}


@dataclass(frozen=True)
class CatalogIssue:
    code: str
    message: str


@dataclass
class CatalogValidationReport:
    issues: list[CatalogIssue] = field(default_factory=list)
    item_count: int = 0
    source_count: int = 0
    photo_count: int = 0
    checks_run: int = 0

    @property
    def valid(self) -> bool:
        return not self.issues

    def add(self, code: str, message: str) -> None:
        self.issues.append(CatalogIssue(code, message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "item_count": self.item_count,
            "source_count": self.source_count,
            "photo_count": self.photo_count,
            "checks_run": self.checks_run,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _tokens(value: str) -> set[str]:
    return {token.strip() for token in value.split(";") if token.strip()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_ids(
    report: CatalogValidationReport,
    rows: list[dict[str, str]],
    field_name: str,
    table_name: str,
) -> set[str]:
    values = [row.get(field_name, "").strip() for row in rows]
    report.checks_run += len(values)
    if "" in values:
        report.add("missing_id", f"{table_name} contains a blank {field_name}")
    if len(values) != len(set(values)):
        report.add("duplicate_id", f"{table_name} contains duplicate {field_name} values")
    return set(values)


def validate_catalog(
    catalog_dir: Path = DEFAULT_REAL_DECOR_DIR,
    *,
    verify_manifest: bool = True,
) -> CatalogValidationReport:
    """Validate schema, relationships, bounds, rights and release metadata."""

    report = CatalogValidationReport()
    missing = [name for name in (*CATALOG_FILES, "manifest.json") if not (catalog_dir / name).is_file()]
    if missing:
        report.add("missing_file", f"missing required files: {', '.join(missing)}")
        return report

    items = _read_csv(catalog_dir / "decor_items.csv")
    sources = _read_csv(catalog_dir / "market_sources.csv")
    photos = _read_csv(catalog_dir / "photo_candidates.csv")
    safety = _read_csv(catalog_dir / "safety_profiles.csv")
    authorities = _read_csv(catalog_dir / "authoritative_sources.csv")
    report.item_count = len(items)
    report.source_count = len(sources)
    report.photo_count = len(photos)

    item_ids = _unique_ids(report, items, "item_id", "decor_items.csv")
    source_ids = _unique_ids(report, sources, "source_id", "market_sources.csv")
    photo_ids = _unique_ids(report, photos, "candidate_id", "photo_candidates.csv")
    safety_ids = _unique_ids(report, safety, "safety_profile_id", "safety_profiles.csv")
    authority_ids = _unique_ids(report, authorities, "source_id", "authoritative_sources.csv")
    if not item_ids:
        report.add("empty_catalog", "decor_items.csv is empty")

    legacy_theme_path = catalog_dir.parent / "catalogs" / "themes.csv"
    if not legacy_theme_path.is_file():
        legacy_theme_path = DEFAULT_REAL_DECOR_DIR.parent / "catalogs" / "themes.csv"
    theme_ids = {row["theme_id"] for row in _read_csv(legacy_theme_path)}

    seen_categories: set[str] = set()
    seen_tiers: set[str] = set()
    category_counts = {category: 0 for category in CATEGORIES}
    for row in items:
        report.checks_run += 16
        item_id = row["item_id"]
        category = row["category"]
        seen_categories.add(category)
        seen_tiers.add(row["package_tier"])
        if category in category_counts:
            category_counts[category] += 1
        else:
            report.add("unknown_category", f"{item_id}: {category}")
        if row["package_tier"] not in PACKAGE_TIERS:
            report.add("unknown_tier", f"{item_id}: {row['package_tier']}")
        if not _tokens(row["event_types"]):
            report.add("empty_events", item_id)
        unknown_themes = _tokens(row["theme_ids"]) - theme_ids - {"all"}
        if unknown_themes:
            report.add("unknown_theme", f"{item_id}: {sorted(unknown_themes)}")
        if not _tokens(row["environments"]) <= {"indoor", "outdoor", "semi_outdoor"}:
            report.add("unknown_environment", item_id)
        for numeric_field in (
            "width_cm",
            "depth_cm",
            "height_cm",
            "quantity_min",
            "quantity_max",
            "price_min_pkr",
            "price_max_pkr",
        ):
            try:
                if int(row[numeric_field]) <= 0:
                    raise ValueError
            except (KeyError, ValueError):
                report.add("invalid_positive_number", f"{item_id}: {numeric_field}")
        try:
            if int(row["required_clearance_cm"]) < 0:
                raise ValueError
            if int(row["quantity_min"]) > int(row["quantity_max"]):
                report.add("invalid_quantity_range", item_id)
            if int(row["price_min_pkr"]) > int(row["price_max_pkr"]):
                report.add("invalid_price_range", item_id)
        except (KeyError, ValueError):
            report.add("invalid_range", item_id)
        if row["market_source_id"] not in source_ids:
            report.add("missing_market_source", item_id)
        if row["photo_candidate_id"] not in photo_ids:
            report.add("missing_photo_candidate", item_id)
        if row["safety_profile_id"] not in safety_ids:
            report.add("missing_safety_profile", item_id)
        if row["status"] != "catalog_ready":
            report.add("invalid_item_status", item_id)

    if seen_categories != CATEGORIES:
        report.add("category_coverage", f"found {sorted(seen_categories)}")
    if seen_tiers != PACKAGE_TIERS:
        report.add("tier_coverage", f"found {sorted(seen_tiers)}")
    for category, count in category_counts.items():
        if count < 4:
            report.add("thin_category", f"{category} has only {count} items")

    for row in photos:
        report.checks_run += 10
        candidate_id = row["candidate_id"]
        expected_url = ALLOWED_LICENSES.get(row["license_short_name"])
        if expected_url is None or row["license_url"] != expected_url:
            report.add("unapproved_license", candidate_id)
        if not row["commons_file_page"].startswith("https://commons.wikimedia.org/wiki/File:"):
            report.add("non_commons_photo", candidate_id)
        if not row["creator"].strip() or not row["attribution_text"].strip():
            report.add("incomplete_attribution", candidate_id)
        if row["commercial_reuse"] != "yes" or row["derivatives_allowed"] != "yes":
            report.add("rights_restriction", candidate_id)
        expected_share_alike = "yes" if "BY-SA" in row["license_short_name"] else "no"
        if row["share_alike"] != expected_share_alike:
            report.add("share_alike_mismatch", candidate_id)
        if row["rights_status"] != "page_verified":
            report.add("unverified_rights_status", candidate_id)

    for row in safety:
        report.checks_run += 3
        unknown_sources = _tokens(row["authoritative_source_ids"]) - authority_ids
        if unknown_sources:
            report.add("missing_authoritative_source", f"{row['safety_profile_id']}: {sorted(unknown_sources)}")
        if not row["rules"].strip():
            report.add("missing_safety_rule", row["safety_profile_id"])

    for row in sources:
        report.checks_run += 5
        try:
            low = int(row["observed_price_min"])
            high = int(row["observed_price_max"])
            if low <= 0 or high < low:
                raise ValueError
        except ValueError:
            report.add("invalid_observed_price", row["source_id"])
        if row["currency"] != "PKR":
            report.add("non_pkr_source", row["source_id"])
        if not row["url"].startswith("https://"):
            report.add("invalid_source_url", row["source_id"])

    manifest = json.loads((catalog_dir / "manifest.json").read_text(encoding="utf-8"))
    report.checks_run += 5
    if manifest.get("dataset_id") != "bakesmart-real-decor-catalog-v1":
        report.add("manifest_dataset_id", "unexpected dataset_id")
    if manifest.get("training_approved") is not False:
        report.add("manifest_training_status", "training_approved must be false")
    if manifest.get("recommendation_integration") != "stage_3_pending":
        report.add("manifest_stage_boundary", "recommendation integration must remain pending")
    if verify_manifest:
        manifest_files = {entry["path"]: entry for entry in manifest.get("files", [])}
        if set(manifest_files) != set(CATALOG_FILES):
            report.add("manifest_file_set", f"found {sorted(manifest_files)}")
        for name in CATALOG_FILES:
            report.checks_run += 2
            entry = manifest_files.get(name)
            if entry and entry.get("sha256") != _sha256(catalog_dir / name):
                report.add("checksum_mismatch", name)
            if entry:
                expected_records = len(_read_csv(catalog_dir / name))
                if entry.get("records") != expected_records:
                    report.add("record_count_mismatch", name)
    return report


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _canonical_license_name(value: str) -> str:
    return "CC0 1.0" if value.strip() == "CC0" else value.strip()


def _canonical_license_url(value: str) -> str:
    normalized = value.strip().replace("http://", "https://")
    if normalized.endswith("/deed.en"):
        normalized = normalized[: -len("deed.en")]
    return normalized.rstrip("/") + "/"


def _http_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "BakeSmart/0.5 Stage2 rights verifier"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "BakeSmart/0.5 Stage2 asset collector"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"unsupported response content type: {content_type}")
        data = response.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("image exceeds the 20 MiB collection limit")
    return data


def _commons_title(file_page: str) -> str:
    parsed = urllib.parse.urlparse(file_page)
    title = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]).replace("_", " ")
    if not title.startswith("File:"):
        raise ValueError(f"not a Commons file page: {file_page}")
    return title


def _fetch_commons_imageinfo(
    file_page: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] = _http_json,
) -> dict[str, str]:
    title = _commons_title(file_page)
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "imageinfo",
            "titles": title,
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": "1600",
        }
    )
    payload = fetch_json(f"https://commons.wikimedia.org/w/api.php?{query}")
    pages = payload.get("query", {}).get("pages", [])
    if len(pages) != 1 or not pages[0].get("imageinfo"):
        raise ValueError(f"Commons returned no image metadata for {title}")
    info = pages[0]["imageinfo"][0]
    metadata = info.get("extmetadata", {})

    def meta(name: str) -> str:
        return _strip_html(str(metadata.get(name, {}).get("value", "")))

    return {
        "title": title,
        "download_url": info.get("thumburl") or info.get("url", ""),
        "mime": info.get("mime", ""),
        "license_short_name": meta("LicenseShortName"),
        "license_url": meta("LicenseUrl"),
        "artist": meta("Artist"),
        "credit": meta("Credit"),
        "attribution_required": meta("AttributionRequired"),
    }


def collect_rights_safe_assets(
    catalog_dir: Path = DEFAULT_REAL_DECOR_DIR,
    output_dir: Path | None = None,
    *,
    fetch_metadata: Callable[[str], dict[str, str]] = _fetch_commons_imageinfo,
    download: Callable[[str], bytes] = _download_bytes,
) -> list[dict[str, str]]:
    """Download verified thumbnails and write an attribution/hash manifest."""

    report = validate_catalog(catalog_dir)
    if not report.valid:
        raise ValueError(f"catalogue validation failed: {report.to_dict()}")
    if output_dir is None:
        output_dir = catalog_dir.parents[1] / "runtime" / "real_decor_assets_v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    collected: list[dict[str, str]] = []
    for row in _read_csv(catalog_dir / "photo_candidates.csv"):
        live = fetch_metadata(row["commons_file_page"])
        live_license = _canonical_license_name(live["license_short_name"])
        live_license_url = _canonical_license_url(live["license_url"])
        if live_license != row["license_short_name"]:
            raise ValueError(f"license changed for {row['candidate_id']}")
        if live_license_url != _canonical_license_url(row["license_url"]):
            raise ValueError(f"license URL changed for {row['candidate_id']}")
        if live_license not in ALLOWED_LICENSES:
            raise ValueError(f"non-commercial or unknown license for {row['candidate_id']}")
        if not live["artist"].strip() or not live["download_url"].startswith("https://"):
            raise ValueError(f"incomplete live metadata for {row['candidate_id']}")
        if live["mime"] not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"unsupported image MIME for {row['candidate_id']}")
        extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[live["mime"]]
        target = output_dir / f"{row['candidate_id']}{extension}"
        if target.is_file():
            data = target.read_bytes()
        else:
            data = download(live["download_url"])
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
        collected.append(
            {
                "candidate_id": row["candidate_id"],
                "file": target.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_page": row["commons_file_page"],
                "creator": row["creator"],
                "license": row["license_short_name"],
                "license_url": row["license_url"],
                "attribution": row["attribution_text"],
            }
        )
    manifest_path = output_dir / "asset_attribution_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(collected[0]))
        writer.writeheader()
        writer.writerows(collected)
    return collected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "collect"), nargs="?", default="validate")
    parser.add_argument("--catalog-dir", type=Path, default=DEFAULT_REAL_DECOR_DIR)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        report = validate_catalog(args.catalog_dir)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.valid else 1
    rows = collect_rights_safe_assets(args.catalog_dir, args.output_dir)
    print(json.dumps({"assets_collected": len(rows), "output_dir": str(args.output_dir or "runtime/real_decor_assets_v1")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
