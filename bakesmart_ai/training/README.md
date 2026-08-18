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

Phase 5 implements deterministic local model training:

```powershell
python -m training.train_model --allow-synthetic-bootstrap --evaluate-locked-test
```

The trainer uses NumPy only. It initializes every model parameter from the
configured random seed, trains four recommendation heads over shared hidden
layers, selects the checkpoint using validation loss, and evaluates the locked
test split only when `--evaluate-locked-test` is explicitly supplied. It does
not download weights or call an inference API.

The four heads recommend:

- cake or baked-item style;
- decoration bundle;
- layout and placement strategy; and
- normalized event theme.

Together, those outputs form one scene specification: the cake/baked item,
table, backdrop, decorations and placement must be rendered together in a
single 3D result in a later integration phase. Phase 5 predicts the scene
ingredients; it does not yet generate the 3D geometry or render it.

The generated files in `models/bootstrap_v1/` include pickle-free model
weights, model and data metadata, per-head validation/test metrics, and the
training history. The current 2,400 labels are synthetic bootstrap labels and
`data/manifest.json` keeps `training_approved` set to `false` until independent
expert review is complete. Reported Phase 5 scores measure recovery of those
synthetic rules, not real-world recommendation quality.

A later approved phase will add:

- raw request preprocessing for local inference;
- the FastAPI recommendation-service adapter;
- budget-aware scene itemization and asset lookup;
- one combined interactive 3D scene with cake and decorations; and
- a 2D concept-preview fallback for unsupported devices.
