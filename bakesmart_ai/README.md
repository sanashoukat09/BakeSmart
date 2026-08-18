# BakeSmart AI Service

This directory contains the local Python service for BakeSmart's event-design
recommendation module. It is intentionally separate from the existing Flutter
application and Firebase Cloud Functions.

Phase 2 provides the validated API contract and project structure. Phase 3 adds
versioned design catalogues, a synthetic bootstrap dataset, an expert-review
template, provenance metadata, and strict dataset validation. Phase 4 adds
leakage-safe preprocessing, numeric training matrices, two-reviewer assignments,
agreement auditing, and an explicit training gate. It still does not contain a
trained model or return fabricated recommendations.

## Project rules

- The recommendation model will be trained from randomly initialized weights.
- No Gemini, OpenAI, Claude, Ollama, or other external inference API is used.
- Online models may be studied as technical references, but their APIs and
  trained weights are not dependencies of this service.
- The service runs locally and will later be called by the Flutter app.

## Requirements

- Python 3.11 or newer
- A terminal or PowerShell
- No GPU is required for Phase 2

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

The current recommendation labels are synthetic and pending expert review. See
[`data/README.md`](data/README.md) before using them.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service and model readiness |
| `GET` | `/api/v1/capabilities` | Supported input values |
| `POST` | `/api/v1/designs/validate` | Validate and normalize a design request |
| `POST` | `/api/v1/recommendations` | Reserved for the trained model |

Until the model is created in a later approved phase, the recommendation
endpoint returns HTTP `503` with `model_not_trained`.

## Structure

```text
bakesmart_ai/
├── app/
│   ├── api/          # Versioned HTTP routes
│   ├── core/         # Settings and logging
│   ├── schemas/      # Validated request and response contracts
│   ├── services/     # Recommendation service boundary
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
├── models/           # Trained model artifacts (later phase)
├── training/         # Dataset preparation and training code
└── tests/            # Automated API and schema tests
```
