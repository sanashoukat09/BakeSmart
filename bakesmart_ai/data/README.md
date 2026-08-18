# BakeSmart dataset v1

This directory contains the first versioned dataset for BakeSmart's local event
design recommendation model. The files were extracted without changing values
from the two reviewed Phase 3 source workbooks listed in `manifest.json`.

## What is included

| Group | Files | Records | Purpose |
|---|---:|---:|---|
| Design catalogues | 7 | 322 | Theme, decoration, cake, size, event, placement, and AR asset metadata |
| Recommendation samples | 1 | 2,400 | Structured examples for the future local recommendation model |
| Expert review template | 1 | 120 | Stratified sample for human label review |
| Evaluation cases | 1 | 20 | Safety, fallback, and expected-behaviour checks |

The 2,400 recommendation samples are balanced across six output themes. Their
locked split is 1,680 training, 360 validation, and 360 test rows. Every theme
has 280/60/60 rows in those partitions.

## Critical limitation

The recommendation labels are **synthetic silver labels** produced by a
transparent rule generator. They are not historical orders, customer choices,
or expert decisions. They may be used to build and test the local data and
training pipeline, but they must not be presented as evidence of real-world
recommendation accuracy.

Before final model training and evaluation:

1. a baker and an event decorator must review the 120-row expert template;
2. corrected labels must be stored separately with reviewer identity and role;
3. a real, independently labelled test set must be locked before training;
4. synthetic and human-labelled metrics must be reported separately; and
5. cake serving, structural, allergen, venue, price, and safety claims must be
   confirmed by the responsible professional.

`manifest.json` therefore sets `training_approved` to `false`.

## Validation

Run from `bakesmart_ai`:

```powershell
python -m training.validate_datasets
```

The command checks file checksums, schemas, counts, required values, unique IDs,
catalogue relationships, numeric derivations, class balance, split isolation,
synthetic-label disclosure, and the expert-review sample.

## Phase 4 preparation

Run the deterministic preprocessing pipeline from `bakesmart_ai`:

```powershell
python -m training.prepare_dataset
```

The pipeline keeps the locked 1,680/360/360 split, audits leakage, fits numeric
scaling and categorical vocabularies only on training rows, writes numeric model
inputs under `processed/v1/`, and prepares two independent human-review
assignments for each selected scenario under `review/`.

The preparation report distinguishes a usable synthetic bootstrap pipeline from
production-accuracy training. Production training remains blocked until both
independent reviews and a locked real-world test set exist.

## Change control

- Do not edit a generated CSV by hand.
- Make corrections in a reviewed source or a new explicitly versioned dataset.
- Update the manifest version, checksums, and validation expectations together.
- Never replace the locked test split after model results have been examined.
- Raw workbooks remain outside Git; their SHA-256 hashes identify the exact
  source versions used for this conversion.
