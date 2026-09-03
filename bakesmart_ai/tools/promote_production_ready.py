"""Promote exact, approved GLB revisions to customer production use.

This is intentionally separate from visual review. It fails closed unless the
stored approval matches the current GLB checksum, rights are confirmed, the
live structural validator passes, and both desktop and mobile viewer QA are
explicitly recorded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.production_assets import ProductionAssetRegistry


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "production_assets_v1"
MANIFEST = DATA_DIR / "asset_manifest.csv"
REVIEWS = DATA_DIR / "visual_review_decisions.json"
RECEIPTS = DATA_DIR / "production_promotion_receipts.json"


def _json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return value


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _csv_bytes(fieldnames: list[str], rows: list[dict[str, str]]) -> bytes:
    import io

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def promote_assets(
    asset_ids: list[str],
    *,
    reviewer_id: str,
    desktop_viewer_passed: bool,
    mobile_viewer_passed: bool,
    approve_production: bool,
    manifest_path: Path = MANIFEST,
    review_path: Path = REVIEWS,
    receipts_path: Path = RECEIPTS,
    package_root: Path = ROOT,
) -> list[str]:
    requested = list(dict.fromkeys(asset_ids))
    if not requested:
        raise ValueError("At least one asset ID is required.")
    if not reviewer_id.strip():
        raise ValueError("A reviewer ID is required for the production receipt.")
    if not approve_production:
        raise ValueError("Explicit --approve-production confirmation is required.")
    if not desktop_viewer_passed or not mobile_viewer_passed:
        raise ValueError("Both desktop and mobile BakeSmart viewer QA must pass.")

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        raise ValueError("Production manifest header is missing.")
    by_id = {row["asset_id"]: row for row in rows}
    reviews = _json_object(review_path).get("decisions", {})
    if not isinstance(reviews, dict):
        raise ValueError("Visual review ledger decisions must be an object map.")

    registry = ProductionAssetRegistry(
        data_dir=manifest_path.parent,
        package_root=package_root,
    )
    promoted_at = datetime.now(timezone.utc).isoformat()
    receipt_document = _json_object(receipts_path)
    receipt_rows = receipt_document.get("receipts", {})
    if not isinstance(receipt_rows, dict):
        raise ValueError("Production promotion receipts must be an object map.")

    promoted: list[str] = []
    for asset_id in requested:
        row = by_id.get(asset_id)
        if row is None:
            raise ValueError(f"Unknown production asset '{asset_id}'.")
        if row["production_status"] != "geometry_review":
            raise ValueError(
                f"Asset '{asset_id}' must be in geometry_review before promotion."
            )
        if (
            row["source_license_status"] == "pending_rights_review"
            or row["redistribution_allowed"] != "true"
        ):
            raise ValueError(f"Rights gate failed for asset '{asset_id}'.")
        record = registry.by_asset_id[asset_id]
        glb_path = package_root / record.glb_path
        if not glb_path.is_file():
            raise ValueError(f"Production GLB is missing for asset '{asset_id}'.")
        digest = hashlib.sha256(glb_path.read_bytes()).hexdigest()
        review = reviews.get(asset_id)
        if not isinstance(review, dict) or review.get("decision") != "approve":
            raise ValueError(f"Asset '{asset_id}' does not have an approval decision.")
        if review.get("artifact_sha256") != digest:
            raise ValueError(
                f"Asset '{asset_id}' approval is stale or is not checksum-bound."
            )
        validation = registry.validate_asset(asset_id)
        if validation.errors or validation.status != "not_approved":
            raise ValueError(
                f"Asset '{asset_id}' failed pre-promotion structural validation."
            )
        row["production_status"] = "production_ready"
        receipt_rows[asset_id] = {
            "asset_id": asset_id,
            "catalog_id": row["catalog_id"],
            "artifact_sha256": digest,
            "reviewed_at": review.get("reviewed_at"),
            "reviewer_id": reviewer_id.strip(),
            "desktop_viewer_passed": True,
            "mobile_viewer_passed": True,
            "source_license_status": row["source_license_status"],
            "redistribution_allowed": True,
            "promoted_at": promoted_at,
        }
        promoted.append(asset_id)

    receipt_payload = {
        "receipt_version": "production-promotion-v1",
        "receipts": dict(sorted(receipt_rows.items())),
    }
    _atomic_bytes(
        receipts_path,
        (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    _atomic_bytes(manifest_path, _csv_bytes(fieldnames, rows))

    final_registry = ProductionAssetRegistry(
        data_dir=manifest_path.parent,
        package_root=package_root,
    )
    for asset_id in promoted:
        if final_registry.validate_asset(asset_id).status != "ready":
            raise RuntimeError(
                f"Asset '{asset_id}' did not become renderable after promotion."
            )
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", action="append", required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--desktop-viewer-passed", action="store_true")
    parser.add_argument("--mobile-viewer-passed", action="store_true")
    parser.add_argument("--approve-production", action="store_true")
    args = parser.parse_args()
    promoted = promote_assets(
        args.asset_id,
        reviewer_id=args.reviewer_id,
        desktop_viewer_passed=args.desktop_viewer_passed,
        mobile_viewer_passed=args.mobile_viewer_passed,
        approve_production=args.approve_production,
    )
    print("Production-ready assets:", ", ".join(promoted))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
