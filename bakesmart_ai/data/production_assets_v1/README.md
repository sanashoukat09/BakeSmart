# BakeSmart Production 3D Assets v1

This directory is the canonical **production requirement registry** for BakeSmart's real-catalogue 3D assets. It does not claim that missing/planned GLBs already exist.

## What v1 contains

- `asset_manifest.csv` — one true-size production requirement for every current real decoration catalogue archetype.
- `material_profiles.csv` — PBR authoring profiles used by the Blender/export workflow.
- The current v1 manifest covers 30 real catalogue archetypes. The professional release target remains **80–120 production-ready modular GLBs**, so later stages must split composite sets into reusable modules and add approved variants.

## Coordinate and unit contract

All production assets use metres. A source `.blend` file must contain a root object named `BS_ROOT`. The exporter writes BakeSmart metadata into that root and the local validator requires it in the GLB.

Expected embedded metadata:

- `bakesmart_asset_id`
- `bakesmart_catalog_id`
- `bakesmart_units = metres`
- `bakesmart_dimensions_m = [width, depth, height]` (installation envelope)
- `bakesmart_visible_mesh_bounds_m = [width, depth, height]`
- `bakesmart_collision_envelope_m = [width, depth, height]`
- `bakesmart_anchor_type`
- `bakesmart_scaling_policy`
- `bakesmart_manifest_version = production-assets-v1`

The installation envelope must match the real catalogue dimensions. The validator independently calculates visible GLB bounds from mesh accessors and node transforms. Visible geometry must fill at least 85% of the installation envelope on each axis without exceeding the envelope by more than 2 cm. The collision envelope adds horizontal manifest padding and is used for placement safety rather than visual sizing.

## Scaling rule

Do not stretch a small asset to make it fill a large room. `fixed_true_size` assets stay at true size. `repeat_x` assets are repeated along their approved axis. `modular_cluster` assets use multiple approved modules or instances. Uniform scale limits remain intentionally close to 1.0.

## PBR and mobile budgets

Every production GLB must contain explicit glTF 2.0 `pbrMetallicRoughness` materials. The material profile registry states roughness, metallic, alpha and texture requirements. LOD0/LOD1/LOD2 triangle budgets are stored per asset. Texture atlases are capped at 2048 px in this v1 pipeline.

## Rights gate

A model cannot become `production_ready` while `source_license_status=pending_rights_review` or `redistribution_allowed=false`. Rights confirmation is a human-required step and must not be fabricated.

## Local commands

Validate the registry/work queue:

```powershell
python tools/validate_production_assets.py
```

Validate one asset:

```powershell
python tools/validate_production_assets.py --asset-id prod-backdrop-round-arch
```

Export an approved Blender source:

```powershell
blender --background assets/production_sources/backdrop-round-arch.blend `
  --python tools/blender_export_production_asset.py -- `
  --asset-id prod-backdrop-round-arch
```

The Blender exporter enforces true dimensions, a `BS_ROOT`, visible-bound metadata, PBR node materials and the LOD0 triangle budget before writing the GLB.

## Truth boundary

The Stage-7 renderer can assemble multiple modular GLBs and render supported PBR factors/textures. The normal customer recommendation still renders one combined procedural GLB until approved production modules exist and are integrated into that flow.
