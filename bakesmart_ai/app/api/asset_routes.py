"""Production 3D asset-pipeline endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response

from app.schemas.asset_review import (
    ProductionAssetReviewListResponse,
    ProductionAssetReviewSubmission,
    ProductionAssetReviewSubmissionResponse,
)
from app.schemas.assets import (
    ProductionAssetCatalogResponse,
    ProductionAssetLibrarySummary,
    ProductionAssetValidationRequest,
    ProductionAssetValidationResponse,
    VerticalSliceCelebration,
    VerticalSliceCompositionRequest,
    VerticalSliceCompositionResponse,
    VerticalSliceSummaryResponse,
)
from app.schemas.renderer import (
    RendererCapabilitiesResponse,
    VerticalSliceSceneManifestResponse,
)
from app.services.production_asset_review import production_asset_review_service
from app.services.cake_reference_assets import cake_reference_asset_store
from app.services.production_assets import production_asset_registry
from app.services.professional_renderer import (
    build_vertical_slice_scene,
    renderer_capabilities,
)
from app.services.vertical_slice import vertical_slice_service


router = APIRouter()


@router.get(
    "/assets/3d/cake-references",
    tags=["production assets"],
)
async def cake_reference_catalog() -> dict:
    """List fixed CC0 cake references used only to calibrate procedural cakes."""

    return cake_reference_asset_store.response()


@router.get(
    "/assets/3d/cake-references/{source_id}.glb",
    response_class=FileResponse,
    tags=["production assets"],
)
async def cake_reference_glb(source_id: str) -> FileResponse:
    """Serve a checksum-verified fixed cake model for visual review only."""

    try:
        path = cake_reference_asset_store.glb_path(source_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "unknown_cake_reference", "message": "Unknown cake reference."},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "invalid_cake_reference", "message": str(exc)},
        ) from exc
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="{source_id}-reference.glb"',
            "X-BakeSmart-Reference-Only": "true",
            "X-BakeSmart-Production-Ready": "false",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/assets/3d/summary",
    response_model=ProductionAssetLibrarySummary,
    tags=["production assets"],
)
async def production_asset_summary() -> ProductionAssetLibrarySummary:
    return production_asset_registry.summary()


@router.get(
    "/assets/3d/catalog",
    response_model=ProductionAssetCatalogResponse,
    tags=["production assets"],
)
async def production_asset_catalog() -> ProductionAssetCatalogResponse:
    return production_asset_registry.catalog_response()


@router.post(
    "/assets/3d/validate",
    response_model=ProductionAssetValidationResponse,
    tags=["production assets"],
)
async def validate_production_asset(
    request: ProductionAssetValidationRequest,
) -> ProductionAssetValidationResponse:
    try:
        return production_asset_registry.validate_asset(request.asset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "unknown_production_asset",
                "message": f"Unknown production asset '{request.asset_id}'.",
            },
        ) from exc


@router.get(
    "/assets/3d/production-review",
    response_model=ProductionAssetReviewListResponse,
    tags=["production assets"],
)
async def production_asset_visual_review_queue() -> ProductionAssetReviewListResponse:
    """List actual structurally valid geometry-review GLBs for human review."""

    return production_asset_review_service.candidates()


@router.get(
    "/assets/3d/production-review/{asset_id}.glb",
    response_class=FileResponse,
    tags=["production assets"],
)
async def production_asset_visual_review_glb(asset_id: str) -> FileResponse:
    """Serve the actual production-candidate GLB at true size for review only."""

    try:
        record = production_asset_registry.by_asset_id[asset_id]
        path = production_asset_review_service.glb_path(asset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "unknown_production_asset",
                "message": f"Unknown production asset '{asset_id}'.",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "asset_not_visual_review_candidate",
                "message": str(exc),
            },
        ) from exc
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="{record.catalog_id}-production-review.glb"',
            "X-BakeSmart-Review-Only": "true",
            "X-BakeSmart-Production-Ready": "false",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/assets/3d/production/{asset_id}.glb",
    response_class=FileResponse,
    tags=["production assets"],
)
async def production_asset_customer_glb(asset_id: str) -> FileResponse:
    """Serve only a fully approved, rights-cleared production module."""

    try:
        record = production_asset_registry.by_asset_id[asset_id]
        path = production_asset_registry.customer_glb_path(asset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "unknown_production_asset",
                "message": f"Unknown production asset '{asset_id}'.",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "production_asset_not_customer_ready",
                "message": str(exc),
            },
        ) from exc
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "private, no-cache",
            "Content-Disposition": f'inline; filename="{record.catalog_id}.glb"',
            "X-BakeSmart-Production-Ready": "true",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/assets/3d/production-review/decision",
    response_model=ProductionAssetReviewSubmissionResponse,
    tags=["production assets"],
)
async def save_production_asset_visual_review(
    request: ProductionAssetReviewSubmission,
) -> ProductionAssetReviewSubmissionResponse:
    """Persist human visual-review evidence without changing production status."""

    try:
        return production_asset_review_service.submit(request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "unknown_production_asset",
                "message": f"Unknown production asset '{request.asset_id}'.",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "visual_review_decision_rejected",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/assets/3d/vertical-slice",
    response_model=VerticalSliceSummaryResponse,
    tags=["production assets"],
)
async def professional_vertical_slice() -> VerticalSliceSummaryResponse:
    return vertical_slice_service.summary()


@router.post(
    "/assets/3d/vertical-slice/compose",
    response_model=VerticalSliceCompositionResponse,
    tags=["production assets"],
)
async def compose_professional_vertical_slice(
    request: VerticalSliceCompositionRequest,
) -> VerticalSliceCompositionResponse:
    return vertical_slice_service.compose(request)


@router.get(
    "/assets/3d/renderer/capabilities",
    response_model=RendererCapabilitiesResponse,
    tags=["production assets"],
)
async def professional_renderer_capabilities() -> RendererCapabilitiesResponse:
    """Report Stage-7 renderer support without claiming production assets are ready."""

    return renderer_capabilities()


@router.get(
    "/assets/3d/vertical-slice/scene",
    response_model=VerticalSliceSceneManifestResponse,
    tags=["production assets"],
)
async def professional_vertical_slice_scene(
    celebration: VerticalSliceCelebration,
    usable_focal_width_m: float = Query(gt=0, le=100),
    target_visual_width_m: float = Query(gt=0, le=100),
    include_lighting: bool = True,
) -> VerticalSliceSceneManifestResponse:
    """Assemble independent true-size review modules for the Stage-7 renderer."""

    return build_vertical_slice_scene(
        VerticalSliceCompositionRequest(
            celebration=celebration,
            usable_focal_width_m=usable_focal_width_m,
            target_visual_width_m=target_visual_width_m,
            include_lighting=include_lighting,
        )
    )


@router.get(
    "/assets/3d/review/{asset_id}.glb",
    response_class=Response,
    tags=["production assets"],
)
async def review_production_asset_glb(asset_id: str) -> Response:
    """Serve a generated, structurally validated prototype for review only."""

    try:
        record = production_asset_registry.by_asset_id[asset_id]
        data = vertical_slice_service.review_glb(asset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "unknown_review_asset",
                "message": f"Unknown vertical-slice review asset '{asset_id}'.",
            },
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "review_asset_not_generated",
                "message": f"No review GLB is defined for '{asset_id}'.",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "asset_not_reviewable",
                "message": str(exc),
            },
        ) from exc
    return Response(
        content=data,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="{record.catalog_id}-review.glb"',
            "X-BakeSmart-Review-Only": "true",
            "X-Content-Type-Options": "nosniff",
        },
    )
