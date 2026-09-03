import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.schemas.design import (
    DesignRequest,
    Dimensions,
    ObjectPlacement,
    Position3D,
    SceneSpecification,
)
from app.services.production_assets import ProductionAssetRegistry
from app.services.professional_renderer import build_customer_scene_manifest
from tools.promote_production_ready import promote_assets


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA = PACKAGE_ROOT / "data" / "production_assets_v1"
ASSET_ID = "prod-sign-mirror-welcome"
CATALOG_ID = "sign-mirror-welcome"


def _workspace(tmp_path: Path, *, stale: bool = False) -> tuple[Path, Path, Path]:
    data_dir = tmp_path / "production_assets_v1"
    shutil.copytree(SOURCE_DATA, data_dir)
    glb_path = PACKAGE_ROOT / "app" / "assets" / "production" / f"{CATALOG_ID}.glb"
    digest = hashlib.sha256(glb_path.read_bytes()).hexdigest()
    if stale:
        digest = "0" * 64
    review_path = data_dir / "visual_review_decisions.json"
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
                        "notes": "Passed desktop and mobile visual QA.",
                        "reviewed_at": "2026-09-03T08:00:00Z",
                        "artifact_sha256": digest,
                        "manifest_changed": False,
                        "production_promoted": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return data_dir / "asset_manifest.csv", review_path, data_dir / "receipts.json"


def _promote(tmp_path: Path) -> ProductionAssetRegistry:
    manifest, reviews, receipts = _workspace(tmp_path)
    promoted = promote_assets(
        [ASSET_ID],
        reviewer_id="qa-reviewer-01",
        desktop_viewer_passed=True,
        mobile_viewer_passed=True,
        approve_production=True,
        manifest_path=manifest,
        review_path=reviews,
        receipts_path=receipts,
        package_root=PACKAGE_ROOT,
    )
    assert promoted == [ASSET_ID]
    assert json.loads(receipts.read_text(encoding="utf-8"))["receipts"][ASSET_ID][
        "mobile_viewer_passed"
    ] is True
    return ProductionAssetRegistry(
        data_dir=manifest.parent,
        package_root=PACKAGE_ROOT,
    )


def test_checksum_bound_approval_promotes_exact_glb(tmp_path: Path) -> None:
    registry = _promote(tmp_path)

    assert registry.by_asset_id[ASSET_ID].production_status == "production_ready"
    assert registry.validate_asset(ASSET_ID).status == "ready"
    assert registry.customer_glb_path(ASSET_ID).is_file()


def test_stale_approval_is_rejected(tmp_path: Path) -> None:
    manifest, reviews, receipts = _workspace(tmp_path, stale=True)

    with pytest.raises(ValueError, match="approval is stale"):
        promote_assets(
            [ASSET_ID],
            reviewer_id="qa-reviewer-01",
            desktop_viewer_passed=True,
            mobile_viewer_passed=True,
            approve_production=True,
            manifest_path=manifest,
            review_path=reviews,
            receipts_path=receipts,
            package_root=PACKAGE_ROOT,
        )


def test_both_viewer_sizes_are_required(tmp_path: Path) -> None:
    manifest, reviews, receipts = _workspace(tmp_path)

    with pytest.raises(ValueError, match="desktop and mobile"):
        promote_assets(
            [ASSET_ID],
            reviewer_id="qa-reviewer-01",
            desktop_viewer_passed=True,
            mobile_viewer_passed=False,
            approve_production=True,
            manifest_path=manifest,
            review_path=reviews,
            receipts_path=receipts,
            package_root=PACKAGE_ROOT,
        )


def test_customer_manifest_uses_only_ready_module_at_true_scale(
    tmp_path: Path,
    valid_design_request: dict,
) -> None:
    registry = _promote(tmp_path)
    request = DesignRequest.model_validate(valid_design_request)
    scene = SceneSpecification(
        space=request.space,
        objects=[
            ObjectPlacement(
                asset_id=CATALOG_ID,
                catalog_id=CATALOG_ID,
                role="signage",
                position=Position3D(x_m=1.2, y_m=0.3, z_m=0.0),
                dimensions=Dimensions(width_m=0.75, depth_m=0.05, height_m=1.5),
            )
        ],
        minimum_clearance_m=0.9,
        concept_not_to_scale=False,
        layout_strategy="test",
        asset_status="generated_procedural_glb",
        layers=["decorations"],
    )

    manifest = build_customer_scene_manifest(
        "design-0123456789abcdef0123",
        request,
        scene,
        registry=registry,
    )

    assert manifest.production_module_count == 1
    assert manifest.modules[0].uniform_scale == 1.0
    assert manifest.modules[0].glb_url == (
        f"/api/v1/assets/3d/production/{ASSET_ID}.glb"
    )
    assert manifest.modules[0].translation_m == pytest.approx((-0.3, 0.0, -0.9))
    assert manifest.procedural_fallback_catalog_ids == []
