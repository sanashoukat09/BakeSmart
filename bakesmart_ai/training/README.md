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

Together, those outputs form one scene specification. Phase 6 now maps a
validated API request to the locked 42-feature order, runs the local checkpoint,
selects compatible catalogue records within a decorations-only planning budget,
and returns the cake/baked item, table, backdrop, decorations, lighting and
placement coordinates together. It still does not generate 3D geometry or
claim a working viewer before the referenced assets exist. Phase 7 adds a
separate deterministic procedural renderer: it converts that combined scene
specification into a colored GLB and serves it in a local interactive WebGL
viewer. This does not change or retrain the Phase 5 weights.

The generated files in `models/bootstrap_v1/` include pickle-free model
weights, model and data metadata, per-head validation/test metrics, and the
training history. The current 2,400 labels are synthetic bootstrap labels and
`data/manifest.json` keeps `training_approved` set to `false` until independent
expert review is complete. Reported Phase 5 scores measure recovery of those
synthetic rules, not real-world recommendation quality.

Phase 11 adds a separate venue segmentation bootstrap:

```powershell
python -m training.venue_vision_data
python -m training.train_venue_vision --allow-synthetic-bootstrap --evaluate-locked-test
```

The deterministic scene generator creates exact masks for wall, floor, door,
window, furniture, outlet and walkway. It splits all 240 scenes before pixel
sampling, so pixels from one scene cannot leak across train, validation and
test. The model uses 3×3 RGB patches plus normalized x/y position and reuses
BakeSmart's own NumPy MLP, backpropagation and Adam implementation. All weights
start randomly; no external AI API, pretrained checkpoint or ML framework is
used.

`data/venue_vision/v1/real_annotations_template.csv` defines the source,
licence/consent, annotator and independent-review fields required for future
real images. It currently has zero data rows. Consequently, Phase 11 scores
measure synthetic recovery only and runtime regions are capped below 0.50,
marked unconfirmed and excluded from automatic obstacle or scale decisions.

Phase 12 adds `training.collect_real_venue_photos`. It queries only Wikimedia
Commons metadata, rejects ShareAlike/non-commercial/no-derivatives/GFDL
licences, strips EXIF while resizing candidates, records SHA-256 and perceptual
hashes, and keeps all raw files below ignored `data/venue_vision/raw/real_v2/`.
The frozen audit currently contains 176 CC0/public-domain/CC BY source records.
No row becomes training data until a real photograph passes venue/privacy and
rights review, receives a complete seven-class manual PNG mask, and is accepted
by a different reviewer. The approved-row count remains zero.

An optional external synthetic-data utility is available for additional visual
diversity:

```powershell
python -m training.generate_gemini_venue_images --count 10 --acknowledge-external-synthetic-data
```

It requires `GEMINI_API_KEY` in the process environment, records image and
prompt provenance, and keeps all generated pixels ignored. These outputs are
unlabelled synthetic augmentation candidates, not real photos, approved masks
or evidence of production accuracy.

A later approved phase will add:

- original or redistribution-safe artist-created assets to replace procedural
  placeholder geometry;
- cake-photo reconstruction only after a suitable owned training dataset exists;
- at least 100 independently reviewed, rights-cleared real venue masks for
  domain-gap evaluation;
- actual live-camera AR scenes on supported devices; and
- production deployment and physical-device verification.
