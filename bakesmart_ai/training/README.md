# Training workspace

Phase 3 adds a deterministic dataset validator. Run it before using any data:

```powershell
python -m training.validate_datasets
```

The validator uses only the Python standard library. It checks the versioned
manifest and all catalogue, training, review, and evaluation CSV files.

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
