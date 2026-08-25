from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from app.services.real_decor_catalog import DEFAULT_REAL_DECOR_DIR, RealDecorCatalog
from training.real_decor_catalog_v1 import (
    ALLOWED_LICENSES,
    collect_rights_safe_assets,
    validate_catalog,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_stage2_catalogue_is_complete_and_valid() -> None:
    report = validate_catalog()

    assert report.valid, report.to_dict()
    assert report.item_count == 30
    assert report.source_count == 12
    assert report.photo_count == 10
    assert report.checks_run >= 600

    items = _read_csv(DEFAULT_REAL_DECOR_DIR / "decor_items.csv")
    assert Counter(row["category"] for row in items) == {
        "backdrop": 6,
        "floor-arrangement": 6,
        "lighting": 6,
        "table-setting": 6,
        "signage": 6,
    }
    assert {row["package_tier"] for row in items} == {
        "essential",
        "balanced",
        "statement",
    }


def test_manifest_keeps_stage3_and_training_locked() -> None:
    manifest = json.loads((DEFAULT_REAL_DECOR_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["stage"] == 2
    assert manifest["training_approved"] is False
    assert manifest["recommendation_integration"] == "stage_3_pending"
    assert manifest["customer_output_changed"] is False
    assert manifest["vendor_endorsement"] is False


def test_filter_returns_real_compatible_choices_without_ranking_claim() -> None:
    catalog = RealDecorCatalog()

    wedding = catalog.filter_items(
        event_type="wedding",
        theme_id="floral-romantic",
        environment="indoor",
    )
    kids = catalog.filter_items(
        event_type="kids_birthday",
        theme_id="whimsical-kids",
        environment="indoor",
    )

    assert wedding.items
    assert kids.items
    assert {row["item_id"] for row in wedding.items} != {row["item_id"] for row in kids.items}
    assert {row["category"] for row in wedding.items} >= {
        "backdrop",
        "floor-arrangement",
        "lighting",
        "table-setting",
        "signage",
    }
    assert wedding.total_price_min_pkr > 0
    assert wedding.total_price_max_pkr >= wedding.total_price_min_pkr


def test_every_item_resolves_market_safety_and_photo_evidence() -> None:
    catalog = RealDecorCatalog()

    for item in catalog.items:
        evidence = catalog.evidence_for(item)
        assert evidence["market_source"]["url"].startswith("https://")
        assert evidence["safety_profile"]["rules"]
        assert evidence["photo_candidate"]["commons_file_page"].startswith(
            "https://commons.wikimedia.org/wiki/File:"
        )


def test_validator_rejects_noncommercial_photo_license(tmp_path: Path) -> None:
    copied = tmp_path / "catalog"
    shutil.copytree(DEFAULT_REAL_DECOR_DIR, copied)
    photo_path = copied / "photo_candidates.csv"
    rows = _read_csv(photo_path)
    fieldnames = list(rows[0])
    rows[0]["license_short_name"] = "CC BY-NC 4.0"
    rows[0]["license_url"] = "https://creativecommons.org/licenses/by-nc/4.0/"
    with photo_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report = validate_catalog(copied, verify_manifest=False)

    assert not report.valid
    assert "unapproved_license" in {issue.code for issue in report.issues}


def test_collector_rechecks_live_rights_and_writes_attribution_manifest(tmp_path: Path) -> None:
    photos = _read_csv(DEFAULT_REAL_DECOR_DIR / "photo_candidates.csv")
    indexed = {row["commons_file_page"]: row for row in photos}

    def metadata(file_page: str) -> dict[str, str]:
        row = indexed[file_page]
        return {
            "title": row["title"],
            "download_url": f"https://upload.wikimedia.org/{row['candidate_id']}.jpg",
            "mime": "image/jpeg",
            "license_short_name": row["license_short_name"],
            "license_url": row["license_url"],
            "artist": row["creator"],
            "credit": row["attribution_text"],
            "attribution_required": "true",
        }

    download_calls: list[str] = []

    def download(url: str) -> bytes:
        download_calls.append(url)
        return b"rights-safe-test-image"

    collected = collect_rights_safe_assets(
        output_dir=tmp_path,
        fetch_metadata=metadata,
        download=download,
    )

    assert len(collected) == len(photos) == 10
    assert (tmp_path / "asset_attribution_manifest.csv").is_file()
    assert len(_read_csv(tmp_path / "asset_attribution_manifest.csv")) == 10
    assert all((tmp_path / row["file"]).is_file() for row in collected)
    assert len(download_calls) == 10

    collect_rights_safe_assets(
        output_dir=tmp_path,
        fetch_metadata=metadata,
        download=download,
    )
    assert len(download_calls) == 10


def test_collector_stops_if_live_license_changes(tmp_path: Path) -> None:
    def changed_metadata(file_page: str) -> dict[str, str]:
        return {
            "title": "changed",
            "download_url": "https://upload.wikimedia.org/changed.jpg",
            "mime": "image/jpeg",
            "license_short_name": "CC BY-NC 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
            "artist": "creator",
            "credit": "credit",
            "attribution_required": "true",
        }

    with pytest.raises(ValueError, match="license changed"):
        collect_rights_safe_assets(
            output_dir=tmp_path,
            fetch_metadata=changed_metadata,
            download=lambda url: b"must-not-download",
        )
    assert not list(tmp_path.glob("*.jpg"))


def test_license_allowlist_contains_only_commercial_derivative_licenses() -> None:
    assert ALLOWED_LICENSES == {
        "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
        "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
        "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
        "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    }
