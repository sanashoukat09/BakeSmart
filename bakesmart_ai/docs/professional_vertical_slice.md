# Stage 6 — Professional Vertical Slice

Stage 6 adds the first concrete, true-size 3D review set for Birthday, Wedding, and South Asian Mehndi without weakening the Stage 5 production approval gates.

## What is implemented

BakeSmart now generates 12 deterministic low-poly GLB review assets locally from source code. The review assets cover four roles per celebration: backdrop, support décor, lighting/table décor, and signage/table accents.

Birthday: Chiara panels, balloon clusters, light curtain, foamboard welcome sign.

Wedding: floral arch, floral pedestal pair, low floral centerpiece, LED candle set.

South Asian Mehndi: layered stage, marigold clusters, Mehndi textile/brass-look table set, festoon lights.

The generator uses only local Python code. No hosted AI, remote inference, pretrained asset generator, or external 3D service is used.

## True-size rule

Every review GLB embeds the production asset id, catalogue id, metre units, anchor type, and exact catalogue dimensions. Composition always returns `uniform_scale=1.0`.

Important examples:

- Birthday Chiara backdrop: 2.60 × 0.65 × 2.20 m
- Wedding floral arch: 2.80 × 0.90 × 2.50 m
- South Asian stage: 5.00 × 1.80 × 3.00 m
- Festoon module: 10.00 × 0.06 × 0.06 m

If a structure does not fit the confirmed focal span, the planner rejects or omits it. It does not shrink/stretch fixed décor to force a fit.

## Review-only boundary

The generated GLBs are geometry/scale prototypes, not artist-approved photorealistic production assets. They are validated against the Stage 5 GLB contract but are not placed in the production asset folder and do not change production readiness.

The production manifest therefore remains truthful: 30 production requirements, 30 production GLBs still missing, 0 production-approved GLBs, and the 80–120 final modular asset target still pending.

## API

`GET /api/v1/assets/3d/vertical-slice` reports the three celebrations, review asset availability, structural validity, blockers, and customer-runtime readiness.

`POST /api/v1/assets/3d/vertical-slice/compose` produces true-size review placements for a confirmed usable focal width and target visual width.

`GET /api/v1/assets/3d/review/{asset_id}.glb` serves a generated structurally validated review GLB and marks the response with `X-BakeSmart-Review-Only: true`.

## Scale-aware composition behavior

Birthday keeps the 2.60 m Chiara backdrop unchanged and adds separate balloon/sign/light modules when the venue has enough span.

Wedding keeps the 2.80 m floral arch unchanged and increases visual spread using separate floral pedestal modules. Tabletop items remain review anchors until the actual cake-table dimensions are known.

Mehndi keeps the 5.00 m stage unchanged. A smaller confirmed span is rejected rather than shrinking the stage. The 10.00 m festoon is omitted unless it physically fits.

## Local QA generation

Run from `bakesmart_ai`:

```powershell
python tools/generate_vertical_slice_assets.py
```

This writes review-only GLBs to `app/assets/review_vertical_slice/` for manual QA.

## What is still not done

The current customer viewer still uses the existing procedural scene output. Full external multi-GLB scene assembly, UV/textured PBR rendering, artist-reviewed materials, contact shadows, object selection/editing, LOD switching, and the final 80–120 production asset library remain future work.

The next implementation stage should be Stage 7: renderer + modular scene assembly upgrade.
