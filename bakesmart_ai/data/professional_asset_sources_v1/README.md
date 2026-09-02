# Professional Asset Source Collection v1

This directory is the provenance gate for BakeSmart's professional 3D asset library.

## Rules

- Only sources with an explicitly verified license enter `approved_source`.
- `approved_source` currently means CC0/public-domain material that may be downloaded, adapted and redistributed. It does **not** mean the asset is production-ready.
- AI-generated source assets are excluded from the approved queue.
- Ambiguous marketplace licenses stay in `excluded_candidates.csv` until a human resolves the conflict.
- Downloaded files must be measured in metres, visually reviewed, optimized to BakeSmart LOD budgets, converted to the production GLB contract and validated before they can move into `app/assets/production/`.
- Third-party model dimensions are never trusted as BakeSmart scene scale until their local bounds are checked.
- Raw source archives belong in `assets/third_party_cc0/raw/` and are not committed by default.

## Collected source batches

The registry now contains **77 vetted CC0 source records** across three source manifests.

Batch 1 (`source_manifest.csv`) contains 24 sources for balloons, structural arches, vases/brass props, dessert display, candles, tables/chairs, PBR materials and event-lighting HDRIs.

Batch 2 (`source_manifest_batch2.csv`) adds 40 sources for:

- ceramic and brass floral vessels;
- realistic and low-poly greenery;
- flower geometry for modular bouquet/garland authoring;
- mirrors and picture/sign frames;
- chandeliers, lanterns and modern hanging lights;
- event furniture and outdoor table/chair sources;
- columns/pedestals and lightweight structural frames;
- wooden/directional signage;
- dessert/market display structures;
- broad Kenney CC0 furniture/nature/holiday/retro packs;
- velvet, marble, terrazzo, concrete and plaster PBR materials.

Batch 3 (`source_manifest_batch3.csv`) adds 13 sources verified from official provider pages on 1 September 2026:

- six outdoor HDRIs covering formal garden, terrace, courtyard, floral tent, pure sunset sky and park sunset lighting;
- four fabric PBR sources covering satin, sheer georgette, linen and matte cotton;
- two realistic Poly Haven cake models as material, proportion and mobile-optimization references;
- the Kenney CC0 Food Kit as a cake/dessert blocking and mobile-LOD source.

The first acquisition slice downloaded and checksum-verified all 12 automatically supported Poly Haven sources from Batch 3: two cakes, four complete five-map fabric sets and six 1K outdoor HDRIs. This produced 36 verified source files totaling 33,562,512 bytes. Exact file receipts live in `download_receipts/`; `acquisition_review_batch1.json` records scale, triangle counts, intended use and the remaining production gates. The Kenney Food Kit remains a manual package-review item because the provider does not expose a stable file-metadata contract to this helper. These sources are useful inputs, but none is labeled `production_ready` before conversion and visual QA.

The current Quaternius site-wide QAL v1.0 conflicts with older pack pages that still display CC0 and prohibits standalone asset redistribution. New direct Quaternius pack downloads therefore stay in `excluded_candidates.csv` as `needs_rights_resolution`. Existing Poly Pizza records remain governed by the explicit per-asset license displayed by that provider and still require a saved provenance record at download time.

GitHub repository search did not reveal an event-specific model library with sufficiently clear per-asset CC0 provenance. A repository code license must never be assumed to license bundled 3D artwork.

The collection intentionally mixes high-detail hero sources with lightweight sources suitable for mobile LODs. A high-detail source is never sent directly to the customer viewer without optimization.

`coverage_matrix.csv` tracks the target number of variants for each production category and identifies which categories still require original BakeSmart modeling. Important remaining specialist gaps include Chiara panels, South Asian Mehndi stages, modular wedding stages, marigold-specific décor, string/fairy light systems, uplights, neon signs, acrylic signage and corporate brand walls.

## Status vocabulary

- `approved_source`: license/provenance is good enough to enter the download and adaptation queue.
- `needs_rights_resolution`: source looks useful but rights are contradictory or incomplete.
- `rejected_for_production`: do not bring this source into BakeSmart production.

## Download workflow

The local helper is:

```powershell
python tools/collect_professional_assets.py --list
python tools/collect_professional_assets.py --source-id ph-ceramic-vase-01
python tools/collect_professional_assets.py --source-id ph-ceramic-vase-01 --download
python tools/collect_professional_assets.py --verify-receipts
```

The helper reads every `source_manifest*.csv` file, checks for duplicate IDs, and automatically plans/downloads Poly Haven sources using ordinary file retrieval. It selects complete 1K WebGL PBR sets instead of isolated texture maps, reuses an existing file only after verifying its provider checksum, and writes tracked provenance/checksum receipts to `download_receipts/`. OpenGameArt, Poly Pizza and Kenney records remain manual-download queue items because their attachment/package URLs are not used as stable metadata contracts by this helper.

The Poly Haven live API is used only by this offline collection helper, not by BakeSmart's runtime AI or recommendation pipeline. The collected assets themselves are CC0. Respect the provider's current API terms and User-Agent requirements when running the helper.

## Production promotion checklist

A downloaded source is not allowed into the production manifest until all are true:

1. source license is still verified;
2. original source/provenance URL is retained;
3. no generative-AI source flag;
4. local file checksum is recorded;
5. exact XYZ bounds are measured in metres;
6. mesh origin/anchor is corrected;
7. PBR materials are reviewed;
8. triangle count fits the LOD budget or optimized LODs are authored;
9. GLB passes `tools/validate_production_assets.py`;
10. a human visually approves the asset for the mapped BakeSmart role.

## Next processing stage

Collection is only the source stage. The next technical stage is to ingest the highest-value sources into Blender/local tooling and produce BakeSmart-owned production derivatives: exact-scale GLBs, correct origins, separated selectable modules, mobile LODs, optimized PBR maps and explicit catalog mappings. The first production slice should prioritize Birthday, Wedding and South Asian Mehndi because those scenes expose the largest realism and scale problems.
