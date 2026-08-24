"""Run BakeSmart's Door/Outlet visual audit.

Usage from ``bakesmart_ai``::

    python -m training.rare_class_audit

Then open http://127.0.0.1:8012. The tool exposes only locked train and
validation scenes. It never edits semantic masks or the Step-3 split.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from training.annotation_workspace import PROJECT_DIR
from training.rare_class_audit_workspace import RareClassAuditWorkspace


STATIC_DIR = PROJECT_DIR / "rare_class_audit"


class AuditSubmission(BaseModel):
    decision: str = Field(min_length=1)
    notes: str | None = None


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="unexpected rare-class audit error")


def create_app(
    *,
    workspace: RareClassAuditWorkspace | None = None,
    static_dir: Path | None = STATIC_DIR,
) -> FastAPI:
    active = workspace or RareClassAuditWorkspace()
    app = FastAPI(
        title="BakeSmart Rare-Class Visual Audit",
        version="1.1.0",
        description="Read-only Door/Outlet audit for train and validation masks.",
    )
    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/static", StaticFiles(directory=Path(static_dir)), name="rare-audit-static")

    @app.get("/")
    def index():
        if static_dir is None or not (Path(static_dir) / "index.html").is_file():
            return JSONResponse({"service": "BakeSmart Rare-Class Visual Audit", "status": "ok"})
        return FileResponse(Path(static_dir) / "index.html")

    @app.get("/api/scenes")
    def scenes():
        try:
            return {"scenes": active.list_scenes(), "summary": active.summary()}
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{scene_id}/detail")
    def detail(scene_id: str):
        try:
            return active.scene_detail(scene_id)
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{scene_id}/image")
    def image(scene_id: str):
        try:
            return Response(
                active.image_png(scene_id),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{scene_id}/overlay")
    def overlay(scene_id: str):
        try:
            return Response(
                active.rare_overlay_png(scene_id),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.get("/api/scenes/{scene_id}/crop/{class_name}/{component_index}")
    def crop(scene_id: str, class_name: str, component_index: int):
        try:
            return Response(
                active.crop_png(scene_id, class_name, component_index),
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except Exception as exc:
            raise _translate_error(exc) from exc

    @app.post("/api/scenes/{scene_id}/audit")
    def audit(scene_id: str, body: AuditSubmission):
        try:
            return active.save_decision(scene_id, body.decision, body.notes)
        except Exception as exc:
            raise _translate_error(exc) from exc

    return app


app = create_app()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
