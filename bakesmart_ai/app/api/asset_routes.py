"""Production 3D asset-pipeline endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.assets import (
    ProductionAssetCatalogResponse,
    ProductionAssetLibrarySummary,
    ProductionAssetValidationRequest,
    ProductionAssetValidationResponse,
)
from app.services.production_assets import production_asset_registry


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
