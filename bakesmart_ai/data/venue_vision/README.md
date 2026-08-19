# Venue Vision Dataset Card

Phase 11 uses seven semantic mask labels:

| ID | Label | Meaning |
|---:|---|---|
| 0 | `wall` | Visible wall/background surface |
| 1 | `floor` | Visible floor surface |
| 2 | `door` | Door or doorway region |
| 3 | `window` | Window region |
| 4 | `furniture` | Furniture blocking the setup area |
| 5 | `outlet` | Visible electrical outlet region |
| 6 | `walkway` | Circulation area that must remain clear |

`v1/synthetic_index.csv` contains 240 deterministic scene seeds split by whole
scene into 70% train, 15% validation and 15% locked test. Images and masks are
rendered from those seeds during training; no generated pixel files need to be
committed. These masks are synthetic bootstrap labels and are not evidence of
accuracy on real customer venues.

`v1/real_annotations_template.csv` is the required manifest for future real
venue images. Each image must have a same-size single-channel PNG mask whose
pixel values use the IDs above. A scene may appear in only one split. Source,
licence or customer consent, annotator, independent reviewer and review status
are mandatory before a row can become training-approved.

Keep private image and mask files under ignored `raw/` folders and reference
them from the v1 manifest with relative paths such as
`../raw/images/scene-001.jpg` and `../raw/masks/scene-001.png`. Running
`python -m training.venue_vision_data` validates path containment, file
existence, matching dimensions, mask IDs, split values, rights/consent and
review fields, then writes `v1/dataset_report.json`. At least 100 approved real
rows are required before the report opens the real-photo training gate.

Current truth and privacy rules:

- No customer venue photo is automatically saved into this dataset.
- Real photos require explicit rights/consent and removal of personal details.
- Synthetic masks are never called expert labels.
- Phase 11 candidate detections are capped below 0.50 confidence.
- Candidates never become confirmed obstacles or physical measurements.
- A real-photo test set and expert review are required before production use.

Architecture ideas were informed by the localisation goal in the original
[U-Net paper](https://arxiv.org/abs/1505.04597), while the room-object label
scope was compared with the official [ADE20K scene parsing dataset](https://ade20k.csail.mit.edu/).
BakeSmart does not download either project's weights or call either project as
an inference service.

## Optional Gemini synthetic augmentation

`python -m training.generate_gemini_venue_images` can create additional
photorealistic-looking synthetic venue candidates through the Gemini API. It
reads `GEMINI_API_KEY` only from the process environment. The key is never
placed in a URL, manifest, prompt or log. Raw images and their resumable
`generation_manifest.csv` stay under ignored
`raw/gemini_synthetic_v1/` storage.

Preview deterministic prompts without a key or network request:

```powershell
python -m training.generate_gemini_venue_images --count 3 --dry-run
```

Generate images after privately setting `GEMINI_API_KEY`:

```powershell
python -m training.generate_gemini_venue_images --count 10 --acknowledge-external-synthetic-data
```

Every output is recorded as `external_ai_generated` and
`unlabelled_not_for_training`. It must pass suitability review and receive a
complete seven-class mask before training. Gemini images cannot enter the
locked real-photo test split and cannot support a real-photo accuracy claim.
