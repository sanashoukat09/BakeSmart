# Production Asset Visual Review

BakeSmart now has a local review-only page for real CC0-derived production candidates that have already passed the structural GLB validator.

## Open the page

From `bakesmart_ai`, run the local FastAPI service in the normal project environment, then open:

`http://127.0.0.1:8000/viewer/production-assets/review`

The page loads the actual candidate GLB with BakeSmart's local Stage-7 WebGL renderer. Each asset is rendered at uniform scale `1.0`; the page does not stretch geometry to make it look larger.

## Decisions

The reviewer can choose `Approve`, `Needs correction`, or `Reject`. Reject and Needs correction require a short note. Decisions are stored locally in `data/production_assets_v1/visual_review_decisions.json`.

An approval is review evidence only. It does **not** update `asset_manifest.csv`, does not set `production_ready`, and does not make the asset customer-renderable. Promotion remains a separate explicit pipeline step after visual/material review.

## Production promotion

After the exact GLB revision is approved in the review page and passes both desktop and mobile BakeSmart viewer QA, run the fail-closed promotion command:

`python -m tools.promote_production_ready --asset-id <prod-id> --reviewer-id <reviewer> --desktop-viewer-passed --mobile-viewer-passed --approve-production`

The command refuses missing or stale checksum-bound approvals, pending rights, failed structural validation, missing viewport QA, and any asset not currently in `geometry_review`. A successful promotion writes an audit receipt and changes only the verified manifest row to `production_ready`.

Ordinary customer recommendations then load that exact module at uniform scale `1.0`. Any selected catalogue items that are not production-ready remain inside the procedural fallback GLB, so a partial production library never exposes an unapproved asset or creates duplicate geometry.

## Current Batch 1

The page discovers built geometry-review candidates and re-runs structural and visible-bounds validation against the actual GLB before listing them. A stored decision is tied to the exact GLB SHA-256 digest; rebuilding an asset automatically makes an older decision stale and returns the new revision to pending review.

Batch 1 contains the CC0-derived low floral centerpiece, Mehndi marigold/brass cluster, and ornate mirror welcome sign. Only candidates that pass the current live validator appear in the queue.
