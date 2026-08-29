from fastapi import APIRouter, HTTPException, status

from app.schemas.design import (
    AreaType,
    CakePhotoUploadRequest,
    DesignRequest,
    EnvironmentType,
    EventType,
    RecommendationResponse,
    TemporaryPhotoAsset,
    ValidationResponse,
    VenuePhotoAnalysis,
    VenuePhotoAnalysisRequest,
    VenueType,
)
from app.schemas.professional import (
    CalibrationValidationRequest,
    CalibrationValidationResponse,
    PlanarCalibrationRequest,
    PlanarCalibrationResponse,
    PlanarProjectionRequest,
    PlanarProjectionResponse,
    ProfessionalCapabilitiesResponse,
    RoomConstraintRequest,
    RoomConstraintResponse,
)
from app.services.calibration import calibration_service
from app.services.recommendation import recommendation_service
from app.services.room_constraints import room_constraint_engine
from app.services.venue_photo_analyzer import venue_photo_analyzer

router = APIRouter()


@router.get(
    "/capabilities",
    response_model=ProfessionalCapabilitiesResponse,
    tags=["designs"],
)
async def capabilities() -> ProfessionalCapabilitiesResponse:
    return ProfessionalCapabilitiesResponse(
        area_types=[item.value for item in AreaType],
        venue_types=[item.value for item in VenueType],
        environment_types=[item.value for item in EnvironmentType],
        event_types=[item.value for item in EventType],
        canonical_units="metres",
        currency="PKR",
        model_ready=recommendation_service.is_ready,
    )


@router.post(
    "/calibration/reference",
    response_model=CalibrationValidationResponse,
    tags=["calibration"],
)
async def validate_calibration_reference(
    request: CalibrationValidationRequest,
) -> CalibrationValidationResponse:
    return calibration_service.validate_reference(request)


@router.post(
    "/calibration/plane",
    response_model=PlanarCalibrationResponse,
    tags=["calibration"],
)
async def calibrate_photo_plane(
    request: PlanarCalibrationRequest,
) -> PlanarCalibrationResponse:
    return calibration_service.calibrate_plane(request)


@router.post(
    "/calibration/plane/project",
    response_model=PlanarProjectionResponse,
    tags=["calibration"],
)
async def project_photo_plane_points(
    request: PlanarProjectionRequest,
) -> PlanarProjectionResponse:
    return calibration_service.project_plane_points(request)


@router.post(
    "/constraints/room",
    response_model=RoomConstraintResponse,
    tags=["constraints"],
)
async def analyze_room_constraints(
    request: RoomConstraintRequest,
) -> RoomConstraintResponse:
    return room_constraint_engine.assess(request)


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
    else:
        warnings.append(
            "A known physical length is recorded, but it does not camera-calibrate the photo by itself. Mark and confirm its image endpoints through the calibration reference step; use four or more confirmed plane correspondences for perspective-correct wall/floor/table projection."
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
    manual_outlets = sum(
        len(photo.manual_outlets) for photo in request.space.photo_evidence
    )
    measured_outlets = sum(
        obstacle.obstacle_type.value == "outlet"
        for obstacle in request.space.obstacles
    )
    if manual_outlets and not measured_outlets:
        warnings.append(
            "Manual Outlet photo marks have no verified scale; add measured Outlet "
            "obstacles when exact 3D clearance is required."
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
    "/design-assets/cake",
    response_model=TemporaryPhotoAsset,
    tags=["venue evidence"],
)
async def upload_cake_photo(
    request: CakePhotoUploadRequest,
) -> TemporaryPhotoAsset:
    try:
        return venue_photo_analyzer.store_cake_photo(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_cake_photo",
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
