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

## First collected batch

`source_manifest.csv` currently records 24 vetted CC0 sources:

- 13 model/model-pack sources for balloons, arches, vases, brass props, dessert display, candles, tables and chairs;
- 6 PBR material sources;
- 5 HDRI lighting environments.

The first batch intentionally favors sources that help Birthday, Wedding, South Asian Mehndi, Baby Shower and Corporate scenes.

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
```

The helper can automatically plan/download Poly Haven sources using ordinary file retrieval. OpenGameArt and Poly Pizza records remain manual-download queue items because their attachment URLs are not stable metadata contracts.

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
