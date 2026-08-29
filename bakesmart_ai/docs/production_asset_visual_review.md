# Production Asset Visual Review

BakeSmart now has a local review-only page for real CC0-derived production candidates that have already passed the structural GLB validator.

## Open the page

From `bakesmart_ai`, run the local FastAPI service in the normal project environment, then open:

`http://127.0.0.1:8000/viewer/production-assets/review`

The page loads the actual candidate GLB with BakeSmart's local Stage-7 WebGL renderer. Each asset is rendered at uniform scale `1.0`; the page does not stretch geometry to make it look larger.

## Decisions

The reviewer can choose `Approve`, `Needs correction`, or `Reject`. Reject and Needs correction require a short note. Decisions are stored locally in `data/production_assets_v1/visual_review_decisions.json`.

An approval is review evidence only. It does **not** update `asset_manifest.csv`, does not set `production_ready`, and does not make the asset customer-renderable. Promotion remains a separate explicit pipeline step after visual/material review.

## Current Batch 1

The page discovers eligible candidates from the build and validation reports. Batch 1 currently contains the CC0-derived low floral centerpiece, Mehndi marigold/brass cluster, and ornate mirror welcome sign.
