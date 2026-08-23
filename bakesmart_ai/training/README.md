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
rights review, receives a complete venue mask, and is accepted by a different
reviewer. The approved-row count remains zero.

## Real venue Step 1: finalize completed annotations

The current real-photo semantic schema has six visual classes only: Wall,
Floor, Door, Window, Furniture and Outlet (IDs 0-5). Walkway is derived from
Floor and stored separately as a binary PNG; it is not a semantic training
class.

After all real venue images have been marked complete in the local labeller,
preview the finalization audit first:

```powershell
python -m training.finalize_real_venue_annotations --dry-run
```

If the dry run reports only expected legacy class-6 migrations and no missing,
invalid or unlabelled masks, run the real finalizer:

```powershell
python -m training.finalize_real_venue_annotations
```

The finalizer checks every `real_v2` image/mask pair, requires matching image
and mask dimensions, accepts only semantic IDs 0-5 plus legacy 6 and draft 255,
reports any remaining 255 pixels, verifies the completion record, migrates
legacy class-6 Walkway pixels to class-1 Floor, and regenerates a separate
binary Walkway mask. Before modifying any legacy mask it copies the original
mask and annotation record into a timestamped backup folder under
`raw/real_v2/backups/annotation_finalization/`. It also writes a JSON report
under `raw/real_v2/annotation_records/finalization_runs/`.

This step never approves masks for training. Successful scenes remain
`not_for_training` and advance only to `ready_for_independent_review`. Independent
human review is the next gate before train/validation/test splitting and real
model training.

## Real venue Step 2: independent mask review

Run the local reviewer from `bakesmart_ai`:

```powershell
python -m training.venue_reviewer
```

Then open `http://127.0.0.1:8011`. The reviewer shows the EXIF-normalized
original photo beside the completed semantic mask and lets a second person
choose `Approve`, `Needs correction`, or `Reject`.

The reviewer must use an ID different from the original annotator ID. Approval
marks the scene `approved_pending_split`; correction keeps it out of training
and requires a short note; rejection marks it rejected and also requires a
note. Review decisions update annotation metadata only: this screen never
changes mask pixels. Once every scene has a final review decision, the next
step is to create the locked train/validation/test split from approved images.

## Real venue Step 3: locked train/validation/test split

After Step 2 has no pending or correction scenes, create the real-data split:

```powershell
python -m training.split_real_venue_dataset
```

Only reviewed scenes with `review_status=approved` are eligible. The splitter
uses a fixed seed and class-presence balancing to spread rarer semantic classes
across train, validation and test while keeping the exact requested 70/15/15
sizes. With 60 approved scenes this produces 42 training, 9 validation and 9
locked test images.

The first successful run writes both `split_manifest.json` and
`split_manifest.csv` under `data/venue_vision/raw/real_v2/splits/`, records the
split in every approved annotation sidecar, and stores SHA-256 checksums for the
image, semantic mask and separate Walkway mask. Re-running the command verifies
and reuses the existing split instead of shuffling it again.

The test set is deliberately locked. Do not train on it, tune model settings
against it, or repeatedly inspect its scores while developing the Step-4 model.
If the approved dataset genuinely changes later, resetting the split requires
both explicit flags:

```powershell
python -m training.split_real_venue_dataset --force-resplit --acknowledge-test-lock-reset
```

That reset should be treated as an exceptional dataset-version change, not a
normal training command.

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
- independently reviewed, rights-cleared real venue masks for domain-gap evaluation;
- actual live-camera AR scenes on supported devices; and
- production deployment and physical-device verification.
