"""Serve generated GLB scenes and BakeSmart's local interactive viewers."""

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
_VERTICAL_SLICE_CELEBRATIONS = {"birthday", "wedding", "south_asian_mehndi"}


def _preview_or_404(design_id: str, package_id: str) -> Path:
    if package_id not in {"essential", "balanced", "statement"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concept preview not found",
        )
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
    return path


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


def _viewer_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data: blob:; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'self'"
        ),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }


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
        headers=_viewer_headers(),
    )


@router.get(
    "/viewer/production-assets/review",
    response_class=FileResponse,
    tags=["viewer"],
)
async def production_asset_review_viewer() -> FileResponse:
    """Open the actual geometry-review GLB queue for human visual inspection."""

    return FileResponse(
        STATIC_DIR / "production_asset_review.html",
        media_type="text/html",
        headers={
            **_viewer_headers(),
            "X-BakeSmart-Review-Only": "true",
            "X-BakeSmart-Production-Ready": "false",
        },
    )


@router.get(
    "/viewer/vertical-slice/{celebration}",
    response_class=FileResponse,
    tags=["viewer"],
)
async def vertical_slice_review_viewer(celebration: str) -> FileResponse:
    """Open the Stage-7 multi-GLB renderer with review-only true-size modules."""

    if celebration not in _VERTICAL_SLICE_CELEBRATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vertical-slice review scene not found",
        )
    return FileResponse(
        STATIC_DIR / "vertical_slice_viewer.html",
        media_type="text/html",
        headers={**_viewer_headers(), "X-BakeSmart-Review-Only": "true"},
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
    "/preview/{design_id}/{package_id}",
    response_class=FileResponse,
    tags=["viewer"],
)
async def responsive_photo_preview(design_id: str, package_id: str) -> FileResponse:
    _preview_or_404(design_id, package_id)
    return FileResponse(
        STATIC_DIR / "preview.html",
        media_type="text/html",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
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
    path = _preview_or_404(design_id, package_id)
    preview_id = f"{design_id}-{package_id}"
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="{preview_id}.png"',
            "X-Content-Type-Options": "nosniff",
        },
    )
