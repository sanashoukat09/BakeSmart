"""Validate CC0 geometry-review GLBs without marking them customer-ready."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.production_assets import ProductionAssetRegistry, inspect_glb_bytes  # noqa: E402

BUILD_REPORT = ROOT / "data/production_assets_v1/production_candidate_build_report.json"
OUTPUT = ROOT / "data/production_assets_v1/production_candidate_validation_report.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-report", type=Path, default=BUILD_REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    registry = ProductionAssetRegistry()
    build = json.loads(args.build_report.read_text(encoding="utf-8"))
    validations = []
    failed = False
    for item in build.get("assets", []):
        asset_id = item["asset_id"]
        record = registry.by_asset_id.get(asset_id)
        if record is None:
            validations.append({"asset_id": asset_id, "valid": False, "errors": ["unknown asset id"]})
            failed = True
            continue
        path = ROOT / record.glb_path
        if not path.is_file():
            validations.append({"asset_id": asset_id, "valid": False, "errors": ["candidate GLB missing"]})
            failed = True
            continue
        checks, errors, warnings, triangles = inspect_glb_bytes(path.read_bytes(), record)
        valid = not errors
        failed = failed or not valid
        validations.append({
            "asset_id": asset_id,
            "valid": valid,
            "file_size_bytes": path.stat().st_size,
            "triangle_count": triangles,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "review_only": True,
        })

    payload = {
        "report_version": "production-candidate-validation-v1",
        "all_structurally_valid": not failed,
        "production_ready": False,
        "human_visual_review_required": True,
        "assets": validations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
