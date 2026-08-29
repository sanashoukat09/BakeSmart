# Third-Party CC0 Asset Workspace

This workspace holds locally downloaded source assets that passed BakeSmart's provenance gate.

- `raw/` — original source archives/files, ignored by Git by default.
- `working/` — optional local Blender conversion/cleanup workspace.
- `review/` — locally exported candidates waiting for scale/material/LOD review.

Do not copy a third-party source directly into `app/assets/production/`. A production asset must preserve provenance, have exact metre dimensions verified locally, satisfy the production GLB validator, meet the mobile LOD/texture budget, and receive human visual approval.

The source registry lives at `data/professional_asset_sources_v1/source_manifest.csv`.
