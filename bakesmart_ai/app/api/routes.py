from fastapi import APIRouter, HTTPException, status

from app.schemas.design import (
    AreaType,
    CapabilitiesResponse,
    DesignRequest,
    EnvironmentType,
    EventType,
    RecommendationResponse,
    ValidationResponse,
    VenueType,
)
from app.services.recommendation import recommendation_service

router = APIRouter()


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    tags=["designs"],
)
async def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        area_types=[item.value for item in AreaType],
        venue_types=[item.value for item in VenueType],
        environment_types=[item.value for item in EnvironmentType],
        event_types=[item.value for item in EventType],
        canonical_units="metres",
        currency="PKR",
        model_ready=recommendation_service.is_ready,
    )


@router.post(
    "/designs/validate",
    response_model=ValidationResponse,
    tags=["designs"],
)
async def validate_design(request: DesignRequest) -> ValidationResponse:
    warnings: list[str] = []
    if not request.space.obstacles:
        warnings.append(
            "No doors, windows, furniture, outlets, stairs, or other obstacles were supplied."
        )
    if request.space.known_reference_m is None:
        warnings.append(
            "No known visual reference measurement was supplied; photo-based scale cannot be verified."
        )

    return ValidationResponse(valid=True, normalized_request=request, warnings=warnings)


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The BakeSmart recommendation model has not been trained yet."
        }
    },
    tags=["recommendations"],
)
async def create_recommendation(request: DesignRequest) -> RecommendationResponse:
    if not recommendation_service.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "model_not_trained",
                "message": "The recommendation endpoint will be enabled after model training.",
            },
        )
    return recommendation_service.recommend(request)
