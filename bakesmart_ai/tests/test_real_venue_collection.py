import csv
import json
from collections import Counter
from pathlib import Path

from training.collect_real_venue_photos import (
    DEFAULT_DISCOVERY_CACHE,
    DEFAULT_MANIFEST,
    _compact_download_url,
    _clean_wikimedia_download_url,
    _license_allowed,
    _looks_suitable,
)


def test_real_source_catalog_is_frozen_but_not_training_approved():
    audit_path = DEFAULT_MANIFEST.parent / "source_audit.csv"
    with audit_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 176
    assert len({row["commons_page_id"] for row in rows}) == 176
    assert all(row["source_page_url"].startswith("https://commons.wikimedia.org/") for row in rows)
    assert all(row["original_url"].startswith("https://upload.wikimedia.org/") for row in rows)
    assert all(row["automated_license_screen"] == "passed" for row in rows)
    assert all(row["training_status"] == "candidate_not_for_training" for row in rows)
    assert not any(
        token in row["license"].upper()
        for row in rows
        for token in ("BY-SA", "NC", "ND", "GFDL")
    )


def test_discovery_cache_and_report_agree_and_keep_gate_closed():
    discovery = json.loads(DEFAULT_DISCOVERY_CACHE.read_text(encoding="utf-8"))
    report_path = DEFAULT_MANIFEST.parent / "collection_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    licence_counts = Counter(
        candidate["license_name"] for candidate in discovery["candidates"]
    )

    assert len(discovery["categories"]) == 26
    assert len(discovery["candidates"]) == report["source_catalog_records"] == 176
    assert dict(sorted(licence_counts.items())) == report["licence_counts"]
    assert report["approved_real_photos"] == 0
    assert report["approved_manual_masks"] == 0
    assert report["training_gate"]["real_photo_training_ready"] is False
    assert report["training_gate"]["real_photo_accuracy_claim_allowed"] is False


def test_real_annotation_template_requires_provenance_and_two_reviewers():
    template_path = DEFAULT_MANIFEST.parent / "real_annotations_template.csv"
    with template_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert len(rows) == 1
    columns = rows[0]
    for required in (
        "source_page_url",
        "license_url",
        "image_sha256",
        "mask_sha256",
        "people_privacy_review",
        "annotator_id",
        "reviewer_id",
        "review_status",
    ):
        assert required in columns


def test_ai_visual_prescreen_is_complete_but_not_human_approval():
    prescreen_path = DEFAULT_MANIFEST.parent / "visual_prescreen_v1.csv"
    with prescreen_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 65
    assert len({row["candidate_id"] for row in rows}) == 65
    assert sum(row["disposition"] == "human_review_pending" for row in rows) == 28
    assert sum(row["disposition"] == "reject" for row in rows) == 37
    assert not any(row["disposition"] == "approved" for row in rows)


def test_licence_and_metadata_filters_are_conservative():
    for allowed in (
        "CC0",
        "CC BY 2.0",
        "CC BY 3.0",
        "CC BY 4.0",
        "Public domain",
    ):
        assert _license_allowed(allowed)
    for rejected in (
        "CC BY-SA 4.0",
        "CC BY-NC 4.0",
        "CC BY-ND 4.0",
        "GFDL",
    ):
        assert not _license_allowed(rejected)

    assert _looks_suitable("empty hotel lobby with chairs")
    assert not _looks_suitable("conference audience and guest speaker")
    assert not _looks_suitable("architectural drawing of a banquet room")
    assert _compact_download_url("https://example.test/960px-room.jpg") == (
        "https://example.test/480px-room.jpg"
    )
    assert _clean_wikimedia_download_url(
        "https://upload.wikimedia.org/a.jpg?utm_source=commons"
    ) == "https://upload.wikimedia.org/a.jpg"
