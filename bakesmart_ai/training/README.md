# Training workspace

Phase 3 adds a deterministic dataset validator. Run it before using any data:

```powershell
python -m training.validate_datasets
```

The validator uses only the Python standard library. It checks the versioned
manifest and all catalogue, training, review, and evaluation CSV files.

Phase 4 adds leakage-safe preprocessing and the independent review workflow:

```powershell
python -m training.prepare_dataset
python -m training.review_dataset
```

Preparation performs the following steps:

1. reruns every Phase 3 integrity check;
2. verifies scenario and feature signatures do not overlap across splits;
3. fits numeric scaling, categorical vocabularies, and target IDs only on the
   1,680 training rows;
4. transforms the frozen 360 validation and 360 test rows;
5. creates two blank, independent human-review assignments for each of the 120
   selected scenarios; and
6. writes checksums, feature order, label mappings, review status, and training
   gate decisions to JSON reports.

Model training is intentionally not implemented yet. The current 2,400 labels
are synthetic bootstrap labels and `data/manifest.json` keeps
`training_approved` set to `false` until independent expert review is complete.

A later approved phase will add:

- preprocessing fitted only on the locked training split;
- a recommendation model initialized from random weights;
- deterministic training and checkpointing;
- separate validation and untouched test evaluation;
- metrics split by synthetic and human-labelled data; and
- model artifact export for the local FastAPI service.
