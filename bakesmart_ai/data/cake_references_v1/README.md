# Cake reference integration v1

This directory records how the two realistic CC0 cake models influence the
configurable BakeSmart cake generator. The imported meshes are fixed visual
references. They are not substituted for a customer's selected dimensions,
shape, tier count, palette, or decorations.

## Trust boundary

- `manifest.json` records source rights, checksums, measured bounds, and GLB
  package metadata.
- `profiles.json` maps catalogue wording to limited proportion, material, and
  decoration cues. Unknown catalogue IDs use BakeSmart's neutral profile.
- `visual_review.json` records the human-readable review of the two packaged
  references and their prohibited uses.
- `generated_review_manifest.json` records representative configurable outputs
  and confirms that their requested dimensions were preserved.
- `review_renders/` and `generated_review_renders/` are diagnostic images for
  inspection; they are not customer-facing product imagery.

Every imported model is marked `reference_only=true`,
`production_ready=false`, and `configurable=false`. Generated customer cakes
remain `cake_remains_configurable=true`.

## Rebuild and review

Run from `bakesmart_ai/` after the ignored source downloads and receipts are
present:

```bash
python tools/package_cake_references.py
python tools/render_cake_reference_review.py
python tools/render_configurable_cake_review.py
pytest tests/test_cake_references.py tests/test_glb_builder.py tests/test_api.py
```

The first command creates deterministic self-contained GLBs. The next two
commands render the actual packaged geometry and three generated variants for
diagnostic review. Before changing `production_ready`, also inspect both fixed
references and representative generated cakes in the BakeSmart WebGL viewer on
desktop and a representative mobile device.

The diagnostic renderer includes geometry, normals, vertex colors, and embedded
base-color textures. It does not reproduce the final WebGL normal-map or
metallic-roughness response, so it cannot replace that final device review.
