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

## Project rules

- The recommendation model will be trained from randomly initialized weights.
- No Gemini, OpenAI, Claude, Ollama, or other external inference API is used.
- Online models may be studied as technical references, but their APIs and
  trained weights are not dependencies of this service.
- The service runs locally and will later be called by the Flutter app.

## Requirements

- Python 3.11 or newer
- A terminal or PowerShell
- No GPU is required for the current local bootstrap model

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

The current recommendation labels are synthetic and pending expert review. See
[`data/README.md`](data/README.md) before using them.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service and model readiness |
| `GET` | `/api/v1/capabilities` | Supported input values |
| `POST` | `/api/v1/designs/validate` | Validate and normalize a design request |
| `POST` | `/api/v1/recommendations` | Run local inference and return one budget-aware scene specification |
| `GET` | `/viewer/{design_id}` | Open the local interactive 3D viewer |
| `GET` | `/api/v1/designs/{design_id}/scene.glb` | Download the generated combined GLB scene |

The recommendation endpoint now loads the verified local Phase 5 checkpoint and
returns the cake, cake table, decorations, backdrop, lighting and coordinates in
one response. Phase 7 procedurally builds those layers into one glTF 2.0 binary
scene, stores it under the ignored runtime directory, and returns a real local
`Open Interactive 3D View` link plus a direct GLB link. The viewer uses no CDN or
external service.

The current geometry is a colored procedural representation, not a reconstruction
of the uploaded cake photograph or a replacement for detailed artist-created
catalogue assets. AR remains unset until a supported client performs device
capability detection. If GLB generation fails, the API keeps the honest
`Concept preview—not to scale` fallback and does not create a fake button.

The returned PKR values are synthetic planning estimates rather than current
vendor or bakery prices. The supplied budget applies to decorations only; cake
cost is shown separately and requires a bakery quote.

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
│   ├── training/     # Bootstrap samples, expert-review template and eval cases
│   ├── processed/v1/ # Numeric split matrices and frozen preprocessing metadata
│   ├── review/       # Two-reviewer assignments, instructions and status report
│   ├── manifest.json # Source hashes, file hashes, counts and review status
│   ├── README.md     # Dataset card, limitations and change control
│   ├── raw/          # Local source workbooks; ignored by Git
│   └── processed/    # Future generated model inputs; ignored by Git
├── models/           # Versioned local bootstrap model artifacts
├── runtime/scenes/   # Generated customer GLB scenes; ignored by Git
├── training/         # Dataset preparation, training, metrics and local runtime
└── tests/            # Automated API and schema tests
```

The exporter follows the official
[Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
