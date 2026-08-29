from pathlib import Path

import pytest

from app.schemas.asset_review import ProductionAssetReviewSubmission
from app.services.production_asset_review import ProductionAssetReviewService
from app.services.production_assets import production_asset_registry


def test_real_geometry_review_queue_contains_built_candidates(tmp_path: Path) -> None:
    service = ProductionAssetReviewService(
        registry=production_asset_registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    response = service.candidates()
    ids = {asset.asset_id for asset in response.assets}
    assert {
        "prod-table-low-floral",
        "prod-floor-marigold-clusters",
        "prod-sign-mirror-welcome",
    } <= ids
    assert response.production_ready is False
    assert all(asset.true_size_scale == 1.0 for asset in response.assets)
    assert all(asset.customer_renderable is False for asset in response.assets)
    assert all(asset.structurally_valid for asset in response.assets)


def test_approve_records_review_without_promoting_manifest(tmp_path: Path) -> None:
    service = ProductionAssetReviewService(
        registry=production_asset_registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    result = service.submit(
        ProductionAssetReviewSubmission(
            asset_id="prod-table-low-floral",
            decision="approve",
        )
    )
    assert result.record.decision == "approve"
    assert result.record.production_promoted is False
    assert result.record.manifest_changed is False
    assert production_asset_registry.by_asset_id["prod-table-low-floral"].production_status == "geometry_review"
    saved = service.candidates()
    selected = next(asset for asset in saved.assets if asset.asset_id == "prod-table-low-floral")
    assert selected.decision is not None
    assert selected.decision.decision == "approve"


def test_correction_and_reject_require_notes(tmp_path: Path) -> None:
    service = ProductionAssetReviewService(
        registry=production_asset_registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    with pytest.raises(ValueError, match="require a short reviewer note"):
        service.submit(
            ProductionAssetReviewSubmission(
                asset_id="prod-floor-marigold-clusters",
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
                asset_id="prod-backdrop-round-arch",
                decision="approve",
            )
        )


def test_review_glb_revalidates_and_stays_true_size(tmp_path: Path) -> None:
    service = ProductionAssetReviewService(
        registry=production_asset_registry,
        review_path=tmp_path / "visual_reviews.json",
    )
    path = service.glb_path("prod-sign-mirror-welcome")
    assert path.name == "sign-mirror-welcome.glb"
    assert path.is_file()
