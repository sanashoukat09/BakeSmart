from app.schemas.assets import VerticalSliceCompositionRequest
from app.services.production_assets import (
    inspect_glb_bytes,
    production_asset_registry,
)
from app.services.vertical_slice import SLICE_ASSETS, vertical_slice_service


def test_vertical_slice_has_twelve_structurally_valid_review_glbs():
    summary = vertical_slice_service.summary()
    assert summary.geometry_review_assets_present is True
    assert summary.customer_runtime_ready is False
    assert len(summary.celebrations) == 3
    assert sum(item.required_asset_count for item in summary.celebrations) == 12
    for celebration in summary.celebrations:
        assert celebration.present_glb_count == celebration.required_asset_count
        assert celebration.structurally_valid_count == celebration.required_asset_count
        expected_ready = sum(
            production_asset_registry.is_renderable_catalog_item(asset.catalog_id)
            for asset in celebration.assets
        )
        assert celebration.production_ready_count == expected_ready
        assert celebration.customer_slice_ready is False
    wedding = next(
        celebration
        for celebration in summary.celebrations
        if celebration.celebration == "wedding"
    )
    assert wedding.production_ready_count == 3


def test_review_binaries_pass_stage5_structural_contract():
    for slice_assets in SLICE_ASSETS.values():
        for slice_asset in slice_assets:
            record = production_asset_registry.by_asset_id[slice_asset.asset_id]
            data = vertical_slice_service.review_glb(slice_asset.asset_id)
            _, errors, _, triangle_count = inspect_glb_bytes(data, record)
            assert errors == []
            assert triangle_count is not None and triangle_count > 0
            assert production_asset_registry.is_renderable_catalog_item(
                record.catalog_id
            ) is (record.production_status == "production_ready")


def test_birthday_composition_never_stretches_modules():
    result = vertical_slice_service.compose(
        VerticalSliceCompositionRequest(
            celebration="birthday",
            usable_focal_width_m=5.5,
            target_visual_width_m=4.5,
        )
    )
    assert result.status in {"fits", "partial"}
    assert result.achieved_visual_width_m <= 5.5
    assert all(item.uniform_scale == 1.0 for item in result.placements)
    backdrop = next(item for item in result.placements if item.role == "backdrop")
    assert backdrop.true_width_m == 2.6


def test_mehndi_stage_is_rejected_when_true_size_does_not_fit():
    result = vertical_slice_service.compose(
        VerticalSliceCompositionRequest(
            celebration="south_asian_mehndi",
            usable_focal_width_m=4.4,
            target_visual_width_m=4.0,
        )
    )
    assert result.status == "does_not_fit"
    assert result.placements == []
    assert any("5.00 m" in note for note in result.notes)


def test_mehndi_does_not_force_ten_metre_festoon_into_small_span():
    result = vertical_slice_service.compose(
        VerticalSliceCompositionRequest(
            celebration="south_asian_mehndi",
            usable_focal_width_m=7.0,
            target_visual_width_m=6.5,
            include_lighting=True,
        )
    )
    assert all(
        placement.asset_id != "prod-lighting-festoon"
        for placement in result.placements
    )
    assert any("10.00 m festoon" in note for note in result.notes)
