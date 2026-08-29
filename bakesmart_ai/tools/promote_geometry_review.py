"""Promote structurally valid CC0 candidates to geometry_review only.

This never marks an asset production_ready. Visual review remains mandatory.
"""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/production_assets_v1/asset_manifest.csv"
PLAN = ROOT / "data/production_assets_v1/production_batch1_plan.csv"
VALIDATION = ROOT / "data/production_assets_v1/production_candidate_validation_report.json"


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    valid_ids = {item["asset_id"] for item in validation.get("assets", []) if item.get("valid") is True}
    if not valid_ids:
        raise SystemExit("No structurally valid candidates to promote to geometry_review")

    plan_by_id = {row["asset_id"]: row for row in read_csv(PLAN)}
    with MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise SystemExit("Manifest header missing")

    changed = []
    for row in rows:
        if row["asset_id"] not in valid_ids:
            continue
        plan = plan_by_id.get(row["asset_id"])
        if plan is None:
            raise SystemExit(f"Missing batch plan row for {row['asset_id']}")
        if plan["source_license_status"] != "cc0_confirmed" or plan["redistribution_allowed"] != "true":
            raise SystemExit(f"Rights gate failed for {row['asset_id']}")
        if row["production_status"] not in {"planned", "in_authoring", "geometry_review"}:
            raise SystemExit(f"Refusing transition from {row['production_status']} for {row['asset_id']}")
        row["source_license_status"] = "cc0_confirmed"
        row["redistribution_allowed"] = "true"
        row["production_status"] = "geometry_review"
        changed.append(row["asset_id"])

    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("Geometry-review assets:", ", ".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
