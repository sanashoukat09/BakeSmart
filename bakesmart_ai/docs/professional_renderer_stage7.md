# Stage 7 — Local Professional Renderer and Modular Scene Assembly

## Purpose

Stage 7 upgrades the BakeSmart browser renderer without weakening the Stage-5 production-asset gate. It makes the local viewer capable of assembling and rendering multiple independent GLB 2.0 modules at metre-based transforms while the current customer pipeline continues to use its procedural fallback until production assets are approved.

## Implemented

- Local `renderer_core.js` with no CDN/runtime network dependency.
- Multiple GLB modules and multiple glTF mesh/node traversal.
- Embedded GLB geometry with strided accessor support for common glTF component types.
- PBR metallic/roughness factors.
- `baseColorTexture`, `metallicRoughnessTexture`, and `emissiveTexture` when UVs are provided.
- Embedded GLB images plus same-origin image URIs; cross-origin texture loading is rejected.
- Existing BakeSmart `_MATERIAL` per-vertex channels remain supported for procedural fallback scenes.
- Independent module transforms in metres; Stage-6 review composition always uses uniform scale `1.0`.
- Orbit, shift-drag pan, wheel/pinch zoom, reset view, click selection, and selected-object highlighting.
- Deterministic planar contact-shadow pass.
- Review-only Birthday, Wedding, and South Asian Mehndi modular viewer.

## Endpoints

- `GET /api/v1/assets/3d/renderer/capabilities`
- `GET /api/v1/assets/3d/vertical-slice/scene`
- `GET /viewer/vertical-slice/{celebration}`

The scene endpoint returns independent GLB URLs and metre translations rather than merging or stretching geometry.

## Truth boundary

This stage does **not** make the Stage-6 low-poly review GLBs production assets. The production manifest still controls customer eligibility, rights approval, source review, LOD budgets, and production status.

The customer viewer can now use the Stage-7 renderer, but its current scene remains the combined procedural planning GLB until enough production assets pass the Stage-5 gate.

## Still required

- Tangent-space normal maps.
- Image-based/environment lighting and HDR probes.
- Real production LOD1/LOD2 files and runtime LOD switching.
- Artist-reviewed PBR texture sets.
- Production-ready modular GLBs (target 80–120).
- Integration of approved production modules into normal customer recommendation scenes.
- Camera-calibrated photo projection/occlusion.
- Device-class performance benchmarking.
