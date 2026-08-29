"""Lightweight BakeSmart app for production-asset visual review.

This entrypoint intentionally does not import the recommendation or venue-vision
services. It exists so geometry-review GLBs can be inspected on low-memory
machines without loading NumPy/PyTorch/ONNX/OpenMP model runtimes.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.asset_routes import router as asset_router
from app.api.viewer import STATIC_DIR, router as viewer_router


app = FastAPI(
    title="BakeSmart Production Asset Review",
    version=__version__,
    description=(
        "Review-only local server for inspecting BakeSmart production-candidate "
        "GLBs. No recommendation or venue-vision model is loaded by this entrypoint."
    ),
)

app.include_router(asset_router, prefix="/api/v1")
app.include_router(viewer_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["system"])
async def review_health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "BakeSmart Production Asset Review",
        "version": __version__,
        "review_only": True,
        "ml_runtime_loaded": False,
    }
