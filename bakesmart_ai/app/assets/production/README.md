# Production GLBs

Only GLBs that pass `tools/validate_production_assets.py` and have `production_status=production_ready` with confirmed redistribution rights may be treated as customer-facing production assets.

File names are fixed by `data/production_assets_v1/asset_manifest.csv`. Planned/missing files intentionally fall back to procedural planning geometry.
