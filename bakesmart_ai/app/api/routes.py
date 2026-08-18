from fastapi import APIRouter, HTTPException, status

from app.schemas.design import (
    AreaType,
    CapabilitiesResponse,
    DesignRequest,
    EnvironmentType,
    EventType,
    RecommendationResponse,
    ValidationResponse,
    VenuePhotoAnalysis,
    VenuePhotoAnalysisRequest,
    VenueType,
)
from app.services.recommendation import recommendation_service
from app.services.venue_photo_analyzer import venue_photo_analyzer

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
    if not request.space.obstacle_map_confirmed:
        warnings.append(
            "The obstacle map is not customer-confirmed; doors, windows, furniture, outlets, stairs, and walkways require review."
        )
    if request.space.known_reference_m is None:
        warnings.append(
            "No known visual reference measurement was supplied; photo-based scale cannot be verified."
        )
    if not request.space.photo_evidence:
        warnings.append("No locally analysed venue photo evidence was supplied.")
    elif not any(
        evidence.angle.value == "second_angle"
        for evidence in request.space.photo_evidence
    ):
        warnings.append(
            "Only one venue angle was supplied; objects outside the frame remain unknown."
        )

    return ValidationResponse(valid=True, normalized_request=request, warnings=warnings)


@router.post(
    "/venue-photos/analyze",
    response_model=VenuePhotoAnalysis,
    tags=["venue evidence"],
)
async def analyze_venue_photo(
    request: VenuePhotoAnalysisRequest,
) -> VenuePhotoAnalysis:
    try:
        return venue_photo_analyzer.analyze(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_venue_photo",
                "message": str(exc),
            },
        ) from exc


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The local BakeSmart model checkpoint is unavailable."
        }
    },
    tags=["recommendations"],
)
async def create_recommendation(request: DesignRequest) -> RecommendationResponse:
    if not recommendation_service.is_ready:
        error_code = (
            "model_not_trained"
            if recommendation_service.status == "not_trained"
            else "model_load_error"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": error_code,
                "message": "The local recommendation checkpoint is not available.",
            },
        )
    return recommendation_service.recommend(request)
