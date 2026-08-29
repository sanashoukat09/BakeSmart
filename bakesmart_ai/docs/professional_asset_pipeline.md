# Stage 5 — Professional 3D Asset Pipeline

## Purpose

Stage 4 made room geometry and scale constraints deterministic. Stage 5 defines what a **real production asset** must look like before BakeSmart is allowed to use it as a customer-facing 3D asset.

This stage deliberately separates three ideas:

1. a catalogue item that exists commercially,
2. a planned 3D requirement for that item,
3. a validated, rights-cleared production GLB.

Only the third is renderable as a production asset.

## Implemented pipeline

### 1. True-size asset manifest

`data/production_assets_v1/asset_manifest.csv` maps every current real decoration catalogue item to a production asset requirement. Each row records exact metre dimensions, expected `.blend`/`.glb` paths, anchor type, fixed/repeat/modular scale policy, strict scale limits, collision padding, PBR material profile, LOD budgets, texture limits, license status and production approval state.

Manifest dimensions are checked against the existing real catalogue at service startup, so the 3D pipeline cannot quietly invent a different physical size.

### 2. PBR material authoring registry

`material_profiles.csv` defines reusable material requirements for painted metal, event board, latex balloons, artificial florals, greenery, glass/acrylic-look objects, LEDs, fabrics, brass-look metal, painted wood, printed boards and mirror-look acrylic. These are authoring contracts, not texture files. Actual texture sources still need rights review.

### 3. Binary GLB validator

`app/services/production_assets.py` validates GLBs locally. It checks GLB/glTF version, mesh/node presence, PBR materials, BakeSmart export metadata, metre units, asset id, anchor type, true-size dimensions within 2 cm, triangle budget and a 25 MB per-module mobile budget.

Texture pixel dimensions and visual material quality still require Blender/export review.

### 4. Rights and approval gate

Even a structurally valid GLB remains `not_approved` until the manifest says `production_ready`, redistribution is allowed, and license status is confirmed.

### 5. Blender-side exporter

`tools/blender_export_production_asset.py` runs inside Blender. It requires `BS_ROOT`, applies mesh scale, verifies true dimensions, requires node-based Principled PBR materials, checks the LOD0 budget, writes BakeSmart metadata and exports a GLB.

### 6. API

The local API exposes:

- `GET /api/v1/assets/3d/summary`
- `GET /api/v1/assets/3d/catalog`
- `POST /api/v1/assets/3d/validate`

These report the real work queue instead of claiming planned assets are finished.

### 7. Recommendation preference

Stage 3 ranking gives a preference to a catalogue item only when its production asset passes the local validator. Budget, event, venue, colour and safety filters still apply first. Because the current manifest is intentionally still planned, existing recommendation behavior remains on the procedural fallback today.

## Current truthful status

- Production pipeline/manifest: implemented.
- Current real-catalogue mappings: 30.
- Material authoring profiles: 14.
- Production-ready GLBs: 0 until real source models, PBR materials and rights are reviewed.
- Professional library target: 80–120 modular production GLBs.
- External modular-GLB scene assembly: not implemented yet.
- Textured PBR customer renderer: not implemented yet.
- Full photo-calibrated 3D projection: not implemented yet.

## Next stage

Build a **professional vertical slice** with actual modular assets for Birthday, Wedding and South Asian Mehndi. Those assets must pass this pipeline before the viewer is upgraded to assemble and render them.
