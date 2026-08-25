# BakeSmart AI Service

This directory contains the local Python service for BakeSmart's event-design
recommendation module. It is intentionally separate from the existing Flutter
application and Firebase Cloud Functions.

Phase 2 provides the validated API contract and project structure. Phase 3 adds
versioned design catalogues, a synthetic bootstrap dataset, an expert-review
template, provenance metadata, and strict dataset validation. Phase 4 adds
leakage-safe preprocessing, numeric training matrices, two-reviewer assignments,
agreement auditing, and an explicit training gate. It still does not contain a
trained production model. Phase 5 adds a small multi-task neural network written
directly with NumPy, deterministic training from random weights, locked-split
evaluation, and a versioned synthetic-bootstrap checkpoint. The checkpoint is
connected to the HTTP recommendation endpoint in Phase 6. Phase 6 also freezes
the raw-request feature adapter, maps predictions to theme/cake/decor catalogue
IDs, applies an explicitly synthetic decorations-only planning budget, checks a
basic obstacle/clearance layout, and returns one combined scene specification.
Phase 7 turns that specification into a real procedural GLB file and serves a
self-contained WebGL viewer with mouse, touch, zoom, reset and GLB download.
Phase 8 connects those endpoints to BakeSmart's authenticated customer Flutter
flow and adds private Firestore save records plus real viewer-link sharing.
Phase 9 adds client-side Android AR-hardware detection and an enforced preview
policy: a real AR URL may be shown only when the device and response both support
it; otherwise the existing interactive 3D or concept fallback is used. Phase 10
adds in-memory venue-photo quality analysis plus customer-confirmed obstacle and
measurement evidence. The scene planner now returns focal-position, clearance,
blocking-item, confidence, observed-fact and assumption results. Phase 11 adds a
seven-class venue segmentation model trained locally from random NumPy weights.
Its synthetic-bootstrap candidates are unconfirmed and never override measured
geometry or the customer-confirmed obstacle map.

Stage 1 photo previews add temporary local venue/cake photo storage, three
budget-and-density decoration packages, and shareable concept PNGs composed
from the customer's real photos. Temporary photos and previews expire after 24
hours and stay under the ignored `runtime/` directory. The procedural GLB is
retained only as an explicitly labelled Basic 3D Layout Preview.

Phase 12 adds an offline, provenance-first Commons collection tool. Its frozen
source audit contains 176 CC0/public-domain/CC BY candidates, but all remain
blocked from training until the image is visually approved, manually masked and
independently reviewed. Raw masks, review decisions, splits and real checkpoints
remain ignored local artifacts, so Git alone does not establish an approved-row
count or real-photo accuracy result.

The real-photo follow-up now includes the six-class annotation finalizer,
independent reviewer, locked 70/15/15 splitter, from-scratch compact U-Net v1,
rare-class v2/v3 experiments, Door/Outlet diagnostics and a protected visual
audit. `training.freeze_real_venue_model` freezes the best checkpoint only
after the audit is fully resolved and common validation comparison succeeds.
`training.evaluate_locked_real_venue_model` then performs the explicit one-time
locked-test evaluation. The customer API prefers that frozen six-class model
only when its matching locked-test report exists; otherwise it safely retains
the synthetic-bootstrap fallback. All predictions remain unconfirmed and do
not provide physical scale.

## Project rules

- The recommendation model will be trained from randomly initialized weights.
- No Gemini, OpenAI, Claude, Ollama, or other external inference API is used.
- Online models may be studied as technical references, but their APIs and
  trained weights are not dependencies of this service.
- The service runs locally and is called by the Phase 8 Flutter event designer.

## Requirements

- Python 3.11 or newer
- A terminal or PowerShell
- No GPU is required for the current local bootstrap model
- Venue-photo analysis uses free local Pillow/NumPy processing and no external API

## Windows setup

```powershell
cd bakesmart_ai
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Create a local environment file if you need to change the defaults:

```powershell
Copy-Item .env.example .env
```

Run the service:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open the local API documentation at `http://127.0.0.1:8000/docs`.

For an Android emulator, the laptop is normally available at
`http://10.0.2.2:8000`. A physical phone on the same Wi-Fi network will use the
laptop's local IPv4 address.

## Tests

```powershell
pytest
```

Validate the Phase 3 data independently:

```powershell
python -m training.validate_datasets
```

Prepare the Phase 4 training inputs and review assignments:

```powershell
python -m training.prepare_dataset
python -m training.review_dataset
```

Train and evaluate the Phase 5 synthetic-bootstrap model:

```powershell
python -m training.train_model --allow-synthetic-bootstrap --evaluate-locked-test
```

Use `--evaluate-locked-test` only for a final evaluation run. Omit it while
changing training settings so the locked test split cannot influence model
selection.

Prepare and train the Phase 11 venue segmentation bootstrap:

```powershell
python -m training.venue_vision_data
python -m training.train_venue_vision --allow-synthetic-bootstrap --evaluate-locked-test
```

This creates no customer-photo copies. It renders deterministic synthetic
images and masks in memory from the locked scene index.

Prepare the Phase 12 rights-screened real-photo candidate pool:

```powershell
python -m training.collect_real_venue_photos --target-count 140
```

This command only downloads and records candidates. It never approves images or
creates masks automatically. See `data/venue_vision/v2/README.md` for the
required visual, privacy, manual annotation and independent-review steps.

The current recommendation labels are synthetic and pending expert review. See
[`data/README.md`](data/README.md) before using them.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service and model readiness |
| `GET` | `/api/v1/capabilities` | Supported input values |
| `POST` | `/api/v1/venue-photos/analyze` | Analyse one JPEG/PNG and keep a temporary local copy for photo previews |
| `POST` | `/api/v1/design-assets/cake` | Keep a validated cake photo locally for up to 24 hours |
| `POST` | `/api/v1/designs/validate` | Validate and normalize a design request |
| `POST` | `/api/v1/recommendations` | Return Essential, Balanced and Statement packages plus the top recommendation |
| `GET` | `/api/v1/designs/{design_id}/previews/{package_id}.png` | Open a real-photo concept preview |
| `GET` | `/viewer/{design_id}` | Open the local interactive 3D viewer |
| `GET` | `/api/v1/designs/{design_id}/scene.glb` | Download the generated combined GLB scene |

The recommendation endpoint now loads the verified local Phase 5 checkpoint and
returns the cake, cake table, decorations, backdrop, lighting and coordinates in
one response. Phase 7 procedurally builds those layers into one glTF 2.0 binary
scene, stores it under the ignored runtime directory, and returns a real local
`Open Basic 3D Layout Preview` link plus a direct GLB link. The viewer uses no CDN or
external service.

The current geometry is a colored procedural representation, not a reconstruction
of the uploaded cake photograph or a replacement for detailed artist-created
catalogue assets. AR remains unset until a supported client performs device
capability detection. If GLB generation fails, the API keeps the honest
`Concept preview—not to scale` fallback and does not create a fake button.
Phase 9 does not change this truth contract: the current response leaves
`ar_supported` and `ar_url` unset, so the customer app never offers AR for the
procedural scene.

Phase 10 photo analysis is intentionally not an object detector. It reports
pixel-derived photo facts and a possible horizontal structural cue. Phase 11
adds synthetic-bootstrap wall, floor, door, window, furniture, outlet and
walkway candidates, but never confirms those candidates or physical scale.
When a frozen and locked-test-evaluated real checkpoint is available locally,
the endpoint instead uses its six semantic classes and derives Walkway from
predicted Floor. It still never confirms obstacles or scale automatically.
The raw JPEG/PNG is resized and stored locally for at most 24 hours so the Stage
1 concept renderer can use the customer's venue and cake pixels. It is not sent
to an external inference service. Placement safety uses only
customer-confirmed dimensions and obstacle coordinates, keeps a minimum 0.90 m
front circulation target, and exposes unknowns in `venue_assessment.assumptions`.

The returned PKR values are synthetic planning estimates rather than current
vendor or bakery prices. The supplied budget applies to decorations only; cake
cost is shown separately and requires a bakery quote.

## Stage 2 real-decoration catalogue

The versioned `data/real_decor_catalog_v1/` directory is the evidence-backed
foundation for the Stage 3 suggestion engine. It contains 30 real-world decor
archetypes across backdrops, floor arrangements, lighting, table settings and
signage, with dimensions, PKR planning ranges, market provenance, safety rules
and rights-checked Wikimedia Commons inspiration candidates.

Stage 2 deliberately does not change customer recommendations. Vendor images
are never copied into the repository, and Commons files may be collected only
after their live API license metadata is rechecked. Validate this release with:

```powershell
python -m training.real_decor_catalog_v1 validate
```

Downloaded inspiration assets are optional Stage 4 inputs and remain under the
ignored runtime directory. Their attribution/hash manifest is generated by the
collector; it is not a substitute for the future visual suitability review.

## Structure

```text
bakesmart_ai/
├── app/
│   ├── api/          # Versioned HTTP routes
│   ├── core/         # Settings and logging
│   ├── schemas/      # Validated request and response contracts
│   ├── services/     # Recommendation service boundary
│   ├── static/       # Dependency-free WebGL viewer, styles and page
│   └── main.py       # FastAPI application
├── data/
│   ├── catalogs/     # Versioned cake, decor, theme, placement and AR catalogues
│   ├── real_decor_catalog_v1/ # Stage 2 real-market decor evidence and rights data
│   ├── training/     # Bootstrap samples, expert-review template and eval cases
│   ├── processed/v1/ # Numeric split matrices and frozen preprocessing metadata
│   ├── review/       # Two-reviewer assignments, instructions and status report
│   ├── venue_vision/ # Synthetic scene index and real-photo annotation contract
│   ├── manifest.json # Source hashes, file hashes, counts and review status
│   ├── README.md     # Dataset card, limitations and change control
│   ├── raw/          # Local source workbooks; ignored by Git
│   └── processed/    # Future generated model inputs; ignored by Git
├── models/           # Recommendation and venue-vision bootstrap checkpoints
├── runtime/          # Temporary photos/previews and generated GLBs; ignored by Git
├── training/         # Dataset preparation, training, metrics and local runtime
└── tests/            # Automated API and schema tests
```

The exporter follows the official
[Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
