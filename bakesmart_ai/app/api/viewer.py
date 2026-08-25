"""Serve generated GLB scenes and BakeSmart's local interactive viewer."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.scene_artifacts import SceneArtifactStore
from app.services.photo_artifacts import PhotoPreviewStore


router = APIRouter()
artifact_store = SceneArtifactStore()
photo_preview_store = PhotoPreviewStore()
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _artifact_or_404(design_id: str) -> Path:
    try:
        path = artifact_store.existing_path(design_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found",
        ) from exc
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scene not found",
        )
    return path


@router.get(
    "/viewer/{design_id}",
    response_class=FileResponse,
    tags=["viewer"],
)
async def interactive_viewer(design_id: str) -> FileResponse:
    _artifact_or_404(design_id)
    return FileResponse(
        STATIC_DIR / "viewer.html",
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/api/v1/designs/{design_id}/scene.glb",
    response_class=FileResponse,
    tags=["viewer"],
)
async def scene_glb(design_id: str) -> FileResponse:
    path = _artifact_or_404(design_id)
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "private, no-cache",
            "Content-Disposition": f'inline; filename="{design_id}.glb"',
        },
    )


@router.get(
    "/api/v1/designs/{design_id}/previews/{package_id}.png",
    response_class=FileResponse,
    tags=["viewer"],
)
async def photo_concept_preview(
    design_id: str,
    package_id: str,
) -> FileResponse:
    preview_id = f"{design_id}-{package_id}"
    try:
        path = photo_preview_store.existing_path(preview_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concept preview not found",
        ) from exc
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concept preview not found",
        )
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="{preview_id}.png"',
            "X-Content-Type-Options": "nosniff",
        },
    )
