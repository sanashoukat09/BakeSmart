import json
import struct

from app.services.production_assets import (
    inspect_glb_bytes,
    production_asset_registry,
)


def _minimal_glb(record, *, dimensions=None):
    embedded_dimensions = dimensions or [
        record.dimensions.width_m,
        record.dimensions.depth_m,
        record.dimensions.height_m,
    ]
    document = {
        "asset": {"version": "2.0"},
        "nodes": [
            {
                "name": "BS_ROOT",
                "mesh": 0,
                "extras": {
                    "bakesmart_asset_id": record.asset_id,
                    "bakesmart_catalog_id": record.catalog_id,
                    "bakesmart_units": "metres",
                    "bakesmart_dimensions_m": embedded_dimensions,
                    "bakesmart_anchor_type": record.anchor_type,
                    "bakesmart_manifest_version": "production-assets-v1",
                },
            }
        ],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 1},
                        "indices": 0,
                        "material": 0,
                    }
                ]
            }
        ],
        "accessors": [
            {"componentType": 5123, "count": 3, "type": "SCALAR"},
            {"componentType": 5126, "count": 3, "type": "VEC3"},
        ],
        "materials": [{"pbrMetallicRoughness": {"metallicFactor": 0.0}}],
    }
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total_length = 12 + 8 + len(payload)
    return (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
    )


def test_production_manifest_covers_current_real_catalogue():
    summary = production_asset_registry.summary()

    assert summary.total_asset_requirements == 30
    assert summary.real_catalog_item_count == 30
    assert summary.mapped_catalog_item_count == 30
    assert summary.material_profile_count == 14
    assert summary.production_ready_count == 3
    assert summary.missing_glb_count == 27
    assert summary.pending_rights_review_count == 27
    assert summary.target_min_assets == 80
    assert summary.target_max_assets == 120
    assert summary.library_target_met is False
    assert summary.runtime_external_glb_assembly_ready is False
    assert summary.pbr_runtime_renderer_ready is False


def test_manifest_requires_true_size_instead_of_large_uniform_stretching():
    assert all(
        asset.min_uniform_scale >= 0.98
        and asset.max_uniform_scale <= 1.02
        for asset in production_asset_registry.assets
    )
    assert any(
        asset.scaling_policy == "repeat_x"
        for asset in production_asset_registry.assets
    )
    assert any(
        asset.scaling_policy == "modular_cluster"
        for asset in production_asset_registry.assets
    )


def test_planned_asset_is_not_claimed_renderable():
    asset = production_asset_registry.assets[0]
    result = production_asset_registry.validate_asset(asset.asset_id)

    assert result.status == "missing_glb"
    assert result.renderable is False
    assert production_asset_registry.is_renderable_catalog_item(asset.catalog_id) is False


def test_binary_inspector_accepts_required_glb_contract():
    asset = production_asset_registry.assets[0]
    checks, errors, warnings, triangles = inspect_glb_bytes(
        _minimal_glb(asset),
        asset,
    )

    assert errors == []
    assert triangles == 1
    assert any("true-size dimensions" in check for check in checks)
    assert any("Texture pixel dimensions" in warning for warning in warnings)


def test_binary_inspector_rejects_wrong_physical_dimensions():
    asset = production_asset_registry.assets[0]
    _, errors, _, _ = inspect_glb_bytes(
        _minimal_glb(asset, dimensions=[9.0, 9.0, 9.0]),
        asset,
    )

    assert any("do not match manifest dimensions" in error for error in errors)


def test_current_candidates_report_independent_visible_and_collision_bounds():
    result = production_asset_registry.validate_asset("prod-sign-mirror-welcome")

    assert result.visible_mesh_bounds_m is not None
    assert result.visible_coverage is not None
    assert result.installation_envelope_m.width_m == 0.75
    assert result.visible_coverage.width_fraction >= 0.85
    assert result.collision_envelope_m.width_m == 0.79
    assert result.collision_envelope_m.depth_m == 0.09


def test_approved_low_floral_passes_true_scale_and_customer_gates():
    result = production_asset_registry.validate_asset("prod-table-low-floral")

    assert result.status == "ready"
    assert result.renderable is True
    assert production_asset_registry.is_renderable_catalog_item(
        "table-low-floral"
    ) is True
    assert production_asset_registry.customer_glb_path(
        "prod-table-low-floral"
    ).is_file()
    assert result.visible_coverage is not None
    assert result.visible_coverage.width_fraction >= 0.85
    assert result.visible_coverage.depth_fraction >= 0.85
    assert result.visible_coverage.height_fraction >= 0.85
    assert result.errors == []
