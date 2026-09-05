"""Move structurally valid Batch 2 CC0 candidates to visual review only."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/production_assets_v1/asset_manifest.csv"
PLAN = ROOT / "data/production_assets_v1/production_batch2_plan.csv"
VALIDATION = ROOT / "data/production_assets_v1/production_candidate_validation_report.json"
CORRECTION_IDS = {
    "prod-backdrop-floral-arch",
}


def rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    valid = {
        item["asset_id"]
        for item in json.loads(VALIDATION.read_text(encoding="utf-8")).get("assets", [])
        if item.get("valid") is True
    }
    plan = {row["asset_id"]: row for row in rows(PLAN)}
    if valid != CORRECTION_IDS:
        raise SystemExit("Validation must pass for exactly the floral-arch correction")
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        manifest = list(reader)
    if not fieldnames:
        raise SystemExit("Manifest header missing")
    for row in manifest:
        if row["asset_id"] not in valid:
            continue
        source = plan[row["asset_id"]]
        if source["source_license_status"] != "cc0_confirmed" or source["redistribution_allowed"] != "true":
            raise SystemExit(f"Rights gate failed for {row['asset_id']}")
        row["source_license_status"] = "cc0_confirmed"
        row["redistribution_allowed"] = "true"
        row["production_status"] = "geometry_review"
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(manifest)
    print("Batch 2 geometry-review assets:", ", ".join(sorted(valid)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
