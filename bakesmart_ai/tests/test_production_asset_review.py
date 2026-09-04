import csv
import json
import shutil
from pathlib import Path

import pytest

from app.schemas.asset_review import ProductionAssetReviewSubmission
from app.services.production_asset_review import ProductionAssetReviewService
from app.services.production_assets import ProductionAssetRegistry, production_asset_registry


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA = PACKAGE_ROOT / "data" / "production_assets_v1"
ASSET_ID = "prod-backdrop-round-arch"


def _review_registry(tmp_path: Path) -> ProductionAssetRegistry:
    data_dir = tmp_path / "production_assets_v1"
    shutil.copytree(SOURCE_DATA, data_dir)
    manifest = data_dir / "asset_manifest.csv"
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for row in rows:
        if row["asset_id"] == ASSET_ID:
            row["production_status"] = "geometry_review"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return ProductionAssetRegistry(data_dir=data_dir, package_root=PACKAGE_ROOT)


def test_real_geometry_review_queue_contains_built_candidates(tmp_path: Path) -> None:
    registry = _review_registry(tmp_path)
    service = ProductionAssetReviewService(
        registry=registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    response = service.candidates()
    ids = {asset.asset_id for asset in response.assets}
    expected = {
        asset.asset_id
        for asset in registry.assets
        if asset.production_status == "geometry_review"
        and registry.validate_asset(asset.asset_id).status == "not_approved"
    }
    assert ids == expected
    assert ASSET_ID in ids
    assert response.production_ready is False
    assert all(asset.true_size_scale == 1.0 for asset in response.assets)
    assert all(asset.customer_renderable is False for asset in response.assets)
    assert all(asset.structurally_valid for asset in response.assets)


def test_approve_records_review_without_promoting_manifest(tmp_path: Path) -> None:
    registry = _review_registry(tmp_path)
    service = ProductionAssetReviewService(
        registry=registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    result = service.submit(
        ProductionAssetReviewSubmission(
            asset_id=ASSET_ID,
            decision="approve",
        )
    )
    assert result.record.decision == "approve"
    assert result.record.production_promoted is False
    assert result.record.manifest_changed is False
    assert result.record.artifact_sha256 is not None
    assert registry.by_asset_id[ASSET_ID].production_status == "geometry_review"
    saved = service.candidates()
    selected = next(asset for asset in saved.assets if asset.asset_id == ASSET_ID)
    assert selected.decision is not None
    assert selected.decision.decision == "approve"


def test_correction_and_reject_require_notes(tmp_path: Path) -> None:
    registry = _review_registry(tmp_path)
    service = ProductionAssetReviewService(
        registry=registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    with pytest.raises(ValueError, match="require a short reviewer note"):
        service.submit(
            ProductionAssetReviewSubmission(
                asset_id=ASSET_ID,
                decision="needs_correction",
            )
        )


def test_planned_asset_cannot_enter_visual_review(tmp_path: Path) -> None:
    service = ProductionAssetReviewService(
        registry=production_asset_registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    with pytest.raises(ValueError, match="not an eligible geometry-review"):
        service.submit(
            ProductionAssetReviewSubmission(
                asset_id="prod-backdrop-chiara-panels",
                decision="approve",
            )
        )


def test_review_glb_revalidates_and_stays_true_size(tmp_path: Path) -> None:
    registry = _review_registry(tmp_path)
    service = ProductionAssetReviewService(
        registry=registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    path = service.glb_path(ASSET_ID)
    assert path.name == "backdrop-round-arch.glb"
    assert path.is_file()


def test_decision_without_matching_artifact_digest_is_stale(tmp_path: Path) -> None:
    registry = _review_registry(tmp_path)
    review_path = tmp_path / "stale_visual_reviews.json"
    review_path.write_text(
        json.dumps(
            {
                "review_version": "production-asset-visual-review-v1",
                "review_only": True,
                "production_ready": False,
                "decisions": {
                    ASSET_ID: {
                        "asset_id": ASSET_ID,
                        "decision": "approve",
                        "notes": "Decision belongs to an older GLB revision.",
                        "reviewed_at": "2026-09-01T08:08:00Z",
                        "manifest_changed": False,
                        "production_promoted": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    service = ProductionAssetReviewService(
        registry=registry,
        review_path=review_path,
    )

    selected = next(
        asset
        for asset in service.candidates().assets
            if asset.asset_id == ASSET_ID
    )

    assert selected.decision is None
