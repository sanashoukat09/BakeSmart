"""Run BakeSmart's independent venue-mask reviewer.

Usage from ``bakesmart_ai``::

    python -m training.venue_reviewer

Open http://127.0.0.1:8011 in a browser. This tool never edits mask pixels;
it only records independent review decisions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from training.annotation_workspace import PROJECT_DIR
from training.venue_review_workspace import VenueReviewWorkspace


STATIC_DIR = PROJECT_DIR / "reviewer"


class ReviewSubmission(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=80)
    decision: str = Field(min_length=1)
    notes: str | None = None


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="unexpected venue review error")


def create_app(
    *,
    review_workspace: VenueReviewWorkspace | None = None,
    static_dir: Path | None = STATIC_DIR,
) -> FastAPI:
    active = review_workspace or VenueReviewWorkspace()
    app = FastAPI(
        title="BakeSmart Venue Mask Reviewer",
        version="1.0.0",
        description="Independent review UI for completed six-class venue masks.",
    )

    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/static", StaticFiles(directory=Path(static_dir)), name="reviewer-static")

    @app.get("/")
    def index():
        if static_dir is None or not (Path(static_dir) / "index.html").is_file():
            return JSONResponse({"service": "BakeSmart Venue Mask Reviewer", "status": "ok"})
        return FileResponse(Path(static_dir) / "index.html")

    @app.get("/api/scenes")
    def scenes(dataset: str = Query(default="real_v2")):
        try:
            return {
                "dataset": dataset,
                "scenes": active.list_scenes(dataset),
                "summary": active.summary(dataset).as_dict(),
            }
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{dataset}/{scene_id}/image")
    def scene_image(dataset: str, scene_id: str):
        try:
            return Response(
                active.normalized_image_png(dataset, scene_id),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{dataset}/{scene_id}/mask-overlay")
    def mask_overlay(dataset: str, scene_id: str):
        try:
            return Response(
                active.mask_overlay_png(dataset, scene_id),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.post("/api/scenes/{dataset}/{scene_id}/review")
    def review(dataset: str, scene_id: str, body: ReviewSubmission):
        try:
            result = active.submit_review(
                dataset_key=dataset,
                scene_id=scene_id,
                reviewer_id=body.reviewer_id,
                decision=body.decision,
                notes=body.notes,
            )
            return {
                **result,
                "summary": active.summary(dataset).as_dict(),
            }
        except Exception as exc:
            raise _translate_error(exc) from exc

    return app


app = create_app()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
