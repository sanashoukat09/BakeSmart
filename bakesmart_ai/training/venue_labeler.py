"""Run BakeSmart's local seven-class venue-mask labelling screen.

Usage from ``bakesmart_ai``::

    python -m training.venue_labeler

The server binds to 127.0.0.1 by default. It writes masks and local annotation
records only under ignored venue-vision raw-data directories.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from training.annotation_workspace import (
    AnnotationWorkspace,
    PROJECT_DIR,
    label_class_payload,
)


STATIC_DIR = PROJECT_DIR / "labeler"


class MaskSubmission(BaseModel):
    mask_png_base64: str = Field(min_length=1)
    annotator_id: str | None = None


class CompleteMaskSubmission(BaseModel):
    mask_png_base64: str = Field(min_length=1)
    annotator_id: str = Field(min_length=1, max_length=80)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="unexpected annotation workspace error")


def create_app(
    *,
    workspace: AnnotationWorkspace | None = None,
    static_dir: Path | None = STATIC_DIR,
) -> FastAPI:
    active_workspace = workspace or AnnotationWorkspace()
    app = FastAPI(
        title="BakeSmart Venue Mask Labeller",
        version="1.0.0",
        description=(
            "Local-only annotation UI for wall, floor, door, window, furniture, "
            "outlet and walkway-candidate masks."
        ),
    )

    if static_dir is not None and Path(static_dir).is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=Path(static_dir)),
            name="labeler-static",
        )

    @app.get("/")
    def index():
        if static_dir is None or not (Path(static_dir) / "index.html").is_file():
            return JSONResponse(
                {
                    "service": "BakeSmart Venue Mask Labeller",
                    "status": "ok",
                }
            )
        return FileResponse(Path(static_dir) / "index.html")

    @app.get("/api/label-classes")
    def label_classes():
        return {
            "classes": label_class_payload(),
            "draft_unlabelled_id": 255,
            "completion_allowed_ids": list(range(7)),
        }

    @app.get("/api/datasets")
    def datasets():
        return {"datasets": active_workspace.dataset_descriptors()}

    @app.get("/api/scenes")
    def scenes(dataset: str = Query(default="real_v2")):
        try:
            return {
                "dataset": dataset,
                "scenes": active_workspace.list_scenes(dataset),
            }
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{dataset}/{scene_id}")
    def scene(dataset: str, scene_id: str):
        try:
            return active_workspace.scene_descriptor(dataset, scene_id)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{dataset}/{scene_id}/image")
    def scene_image(dataset: str, scene_id: str):
        try:
            path = active_workspace.image_path(dataset, scene_id)
            return FileResponse(path)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{dataset}/{scene_id}/mask-overlay")
    def mask_overlay(dataset: str, scene_id: str):
        try:
            return Response(
                active_workspace.overlay_png(dataset, scene_id),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.post("/api/scenes/{dataset}/{scene_id}/validate")
    def validate_mask(dataset: str, scene_id: str, body: MaskSubmission):
        try:
            labels = active_workspace.decode_overlay(
                dataset,
                scene_id,
                body.mask_png_base64,
            )
            return active_workspace.validate_labels(labels)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.post("/api/scenes/{dataset}/{scene_id}/draft")
    def save_draft(dataset: str, scene_id: str, body: MaskSubmission):
        try:
            return active_workspace.save_draft(
                dataset,
                scene_id,
                body.mask_png_base64,
                body.annotator_id,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.post("/api/scenes/{dataset}/{scene_id}/complete")
    def complete_mask(dataset: str, scene_id: str, body: CompleteMaskSubmission):
        try:
            return active_workspace.complete_annotation(
                dataset,
                scene_id,
                body.mask_png_base64,
                body.annotator_id,
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    return app


app = create_app()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
