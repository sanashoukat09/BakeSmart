$ErrorActionPreference = "Stop"

# Keep native numerical runtimes from overcommitting memory on smaller Windows machines.
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"
$env:VECLIB_MAXIMUM_THREADS = "1"
$env:BLIS_NUM_THREADS = "1"

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

Write-Host "Starting BakeSmart production-asset review server..."
Write-Host "This lightweight server does not load recommendation or venue-vision models."
Write-Host "Open http://127.0.0.1:8000/viewer/production-assets/review"

python -m uvicorn app.review_main:app --host 127.0.0.1 --port 8000
