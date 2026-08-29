"""Local CLI for BakeSmart production 3D asset readiness.

Run from bakesmart_ai:
    python tools/validate_production_assets.py
    python tools/validate_production_assets.py --asset-id prod-backdrop-round-arch
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.production_assets import production_asset_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id")
    args = parser.parse_args()

    if args.asset_id:
        try:
            result = production_asset_registry.validate_asset(args.asset_id)
        except KeyError:
            print(json.dumps({"error": "unknown asset", "asset_id": args.asset_id}, indent=2))
            return 2
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return 0 if result.status in {"ready", "missing_glb", "not_approved"} else 1

    summary = production_asset_registry.summary()
    ready_assets = [
        asset.asset_id
        for asset in production_asset_registry.assets
        if asset.production_status == "production_ready"
    ]
    validations = [
        production_asset_registry.validate_asset(asset_id).model_dump(mode="json")
        for asset_id in ready_assets
    ]
    print(
        json.dumps(
            {
                "summary": summary.model_dump(mode="json"),
                "production_ready_validations": validations,
                "note": (
                    "Planned/missing assets are a work queue, not a validator failure. "
                    "Any asset marked production_ready must validate successfully."
                ),
            },
            indent=2,
        )
    )
    return 0 if all(item["status"] == "ready" for item in validations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
