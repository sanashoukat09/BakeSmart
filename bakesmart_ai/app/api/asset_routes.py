"""Production 3D asset-pipeline endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

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
from app.services.production_assets import production_asset_registry
from app.services.professional_renderer import (
    build_vertical_slice_scene,
    renderer_capabilities,
)
from app.services.vertical_slice import vertical_slice_service


router = APIRouter()


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
