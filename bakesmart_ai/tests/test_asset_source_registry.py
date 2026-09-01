import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = ROOT / "data" / "professional_asset_sources_v1"
REGISTRY = REGISTRY_DIR / "source_manifest.csv"
EXCLUDED = ROOT / "data" / "professional_asset_sources_v1" / "excluded_candidates.csv"


def _read(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _all_approved_sources():
    return [
        row
        for path in sorted(REGISTRY_DIR.glob("source_manifest*.csv"))
        for row in _read(path)
    ]


def test_approved_asset_source_registry_is_rights_safe():
    rows = _all_approved_sources()

    assert len(rows) >= 77
    assert len({row["source_id"] for row in rows}) == len(rows)
    assert all(row["collection_status"] == "approved_source" for row in rows)
    assert all(row["license"] == "CC0-1.0" for row in rows)
    assert all(row["license_verified"] == "true" for row in rows)
    assert all(row["redistribution_allowed"] == "true" for row in rows)
    assert all(row["ai_generated"] == "false" for row in rows)
    assert all(row["source_url"].startswith("https://") for row in rows)


def test_first_batch_covers_models_materials_and_lighting():
    rows = _read(REGISTRY)
    types = {row["asset_type"] for row in rows}

    assert {"model", "model_pack", "pbr_material", "hdri"} <= types
    assert any("balloon" in row["primary_bakesmart_use"] for row in rows)
    assert any("brass" in row["primary_bakesmart_use"] for row in rows)
    assert any(row["asset_type"] == "hdri" and "wedding" in row["event_tags"] for row in rows)


def test_expanded_registry_covers_outdoor_lighting_and_cake_sources():
    rows = _all_approved_sources()

    assert sum(row["asset_type"] == "hdri" for row in rows) >= 11
    assert any(row["source_id"] == "kenney-food-kit" for row in rows)
    assert any(row["source_id"] == "ph-strawberry-chocolate-cake" for row in rows)
    assert any(row["source_id"] == "ph-carrot-cake" for row in rows)
    assert any("satin" in row["primary_bakesmart_use"] for row in rows)


def test_ambiguous_or_ai_sources_stay_out_of_approved_registry():
    excluded = _read(EXCLUDED)

    assert excluded
    assert any("AI" in row["observed_license_or_restriction"] for row in excluded)
    assert any(row["status"] == "needs_rights_resolution" for row in excluded)
    assert any(
        row["provider"] == "Quaternius" and row["status"] == "needs_rights_resolution"
        for row in excluded
    )
