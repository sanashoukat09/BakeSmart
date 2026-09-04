import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/production_assets_v1/production_batch2_plan.csv"
SOURCES = ROOT / "data/professional_asset_sources_v1"


def _rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_batch2_contains_six_rights_safe_core_assets():
    rows = _rows(PLAN)
    assert {row["asset_id"] for row in rows} == {
        "prod-backdrop-round-arch",
        "prod-backdrop-balloon-garland",
        "prod-backdrop-floral-arch",
        "prod-lighting-curtain",
        "prod-lighting-uplight-set",
        "prod-lighting-led-candles",
    }
    assert all(row["source_license_status"] == "cc0_confirmed" for row in rows)
    assert all(row["redistribution_allowed"] == "true" for row in rows)


def test_batch2_only_references_registered_cc0_sources():
    sources = {
        row["source_id"]: row
        for path in sorted(SOURCES.glob("source_manifest*.csv"))
        for row in _rows(path)
    }
    referenced = {
        source_id
        for row in _rows(PLAN)
        for key in ("primary_source_id", "secondary_source_id", "tertiary_source_id")
        if (source_id := row[key])
    }
    assert referenced
    assert referenced <= set(sources)
    assert all(sources[source_id]["license"] == "CC0-1.0" for source_id in referenced)
    assert all(sources[source_id]["redistribution_allowed"] == "true" for source_id in referenced)
