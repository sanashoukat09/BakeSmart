"""Read-only access to verified, review-only cake reference GLBs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "cake_references_v1" / "manifest.json"
ASSET_ROOT = ROOT / "app" / "assets" / "cake_references"


class CakeReferenceAssetStore:
    def __init__(self, manifest_path: Path = MANIFEST_PATH, asset_root: Path = ASSET_ROOT):
        self.manifest_path = manifest_path
        self.asset_root = asset_root
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("reference_only") is not True or payload.get("production_ready") is not False:
            raise ValueError("cake reference manifest must remain review-only")
        self.assets = tuple(payload["assets"])
        self.by_source_id = {row["source_id"]: row for row in self.assets}
        if len(self.by_source_id) != len(self.assets):
            raise ValueError("cake reference source ids must be unique")

    def response(self) -> dict[str, Any]:
        return {
            "reference_only": True,
            "production_ready": False,
            "assets": [
                {
                    **row,
                    "glb_url": f'/api/v1/assets/3d/cake-references/{row["source_id"]}.glb',
                }
                for row in self.assets
            ],
        }

    def glb_path(self, source_id: str) -> Path:
        row = self.by_source_id.get(source_id)
        if row is None:
            raise KeyError(source_id)
        path = self.asset_root / row["file_name"]
        if not path.is_file() or path.stat().st_size != int(row["file_size_bytes"]):
            raise ValueError(f"cake reference file is missing or has the wrong size: {source_id}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise ValueError(f"cake reference checksum failed: {source_id}")
        return path


cake_reference_asset_store = CakeReferenceAssetStore()
