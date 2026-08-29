"""Truthful professional-3D capability, calibration, and constraint contracts."""

from typing import Literal

from pydantic import Field

from app.schemas.design import ObjectPlacement, SpaceInput, StrictModel


class PreviewCapabilityState(StrictModel):
    """Machine-readable truth about the currently shipped 3D preview."""

    geometry_mode: Literal["procedural_planning_geometry"] = (
        "procedural_planning_geometry"
    )
    asset_mode: Literal["generated_procedural_glb"] = "generated_procedural_glb"
    renderer_mode: Literal["local_webgl"] = "local_webgl"
    material_mode: Literal["vertex_color_lit"] = "vertex_color_lit"
    metric_scene_coordinates: Literal[True] = True
    camera_navigation_ready: Literal[True] = True
    photo_projection_ready: Literal[False] = False
    full_camera_calibration_ready: Literal[False] = False
    object_editing_ready: Literal[False] = False


class ProfessionalCapabilitiesResponse(StrictModel):
    area_types: list[str]
    venue_types: list[str]
    environment_types: list[str]
    event_types: list[str]
    canonical_units: Literal["metres"]
    currency: Literal["PKR"]
    model_ready: bool
    ai_runtime: Literal["local_only"] = "local_only"
    core_training_policy: Literal["from_scratch_random_initialization"] = (
        "from_scratch_random_initialization"
    )
    external_ai_provider: Literal["none"] = "none"
    scale_source: Literal[
        "customer_confirmed_measurements_and_reference_points"
    ] = "customer_confirmed_measurements_and_reference_points"
    calibration_reference_api_ready: Literal[True] = True
    calibration_plane_api_ready: Literal[True] = True
    planar_projection_api_ready: Literal[True] = True
    metric_room_constraints_ready: Literal[True] = True
    scale_aware_scene_fitting_ready: Literal[True] = True
    preview: PreviewCapabilityState = Field(default_factory=PreviewCapabilityState)


class CalibrationImagePoint(StrictModel):
    """A point in normalized image coordinates, independent of resolution."""

    x_fraction: float = Field(ge=0, le=1)
    y_fraction: float = Field(ge=0, le=1)


class CalibrationReferenceInput(StrictModel):
    """One user-marked physical reference visible in a venue photo."""

    photo_id: str = Field(pattern=r"^venue-photo-[a-f0-9]{20}$")
    label: str = Field(min_length=1, max_length=80)
    start: CalibrationImagePoint
    end: CalibrationImagePoint
    known_length_m: float = Field(gt=0, le=20)
    plane: Literal["wall", "floor", "table", "other"] = "other"
    customer_confirmed: bool = False


class CalibrationValidationRequest(StrictModel):
    image_width_px: int = Field(ge=64, le=20_000)
    image_height_px: int = Field(ge=64, le=20_000)
    reference: CalibrationReferenceInput


class CalibrationValidationResponse(StrictModel):
    status: Literal[
        "reference_recorded",
        "needs_customer_confirmation",
        "invalid_reference",
    ]
    segment_length_px: float = Field(ge=0)
    pixels_per_m_along_reference: float | None = Field(default=None, gt=0)
    metric_reference_ready: bool
    global_projection_ready: Literal[False] = False
    scale_source: Literal[
        "customer_confirmed_reference",
        "unverified_reference",
    ]
    limitations: list[str] = Field(default_factory=list, max_length=10)


class PlaneMetricPoint(StrictModel):
    """Two-dimensional coordinates on one measured physical plane."""

    x_m: float = Field(ge=-100, le=100)
    y_m: float = Field(ge=-100, le=100)


class PlanarCalibrationAnchor(StrictModel):
    """One confirmed image/metric correspondence on a wall, floor, or table."""

    label: str = Field(min_length=1, max_length=80)
    image: CalibrationImagePoint
    plane: PlaneMetricPoint
    customer_confirmed: bool = False


class PlanarCalibrationRequest(StrictModel):
    photo_id: str = Field(pattern=r"^venue-photo-[a-f0-9]{20}$")
    image_width_px: int = Field(ge=64, le=20_000)
    image_height_px: int = Field(ge=64, le=20_000)
    plane_type: Literal["wall", "floor", "table"]
    anchors: list[PlanarCalibrationAnchor] = Field(min_length=4, max_length=20)


class PlanarCalibrationResponse(StrictModel):
    status: Literal[
        "calibrated",
        "needs_customer_confirmation",
        "invalid_geometry",
        "poor_fit",
    ]
    plane_type: Literal["wall", "floor", "table"]
    anchors_used: int = Field(ge=0, le=20)
    confirmed_anchor_count: int = Field(ge=0, le=20)
    homography_m_to_px: list[list[float]] | None = None
    homography_px_to_m: list[list[float]] | None = None
    rms_reprojection_error_px: float | None = Field(default=None, ge=0)
    max_reprojection_error_px: float | None = Field(default=None, ge=0)
    image_coverage_fraction: float = Field(ge=0, le=1)
    fit_quality: Literal["high", "medium", "low", "unavailable"]
    planar_projection_ready: bool
    full_camera_calibration_ready: Literal[False] = False
    limitations: list[str] = Field(default_factory=list, max_length=10)


class PlanarProjectionRequest(StrictModel):
    calibration: PlanarCalibrationRequest
    points_m: list[PlaneMetricPoint] = Field(min_length=1, max_length=100)


class ProjectedPlanePoint(StrictModel):
    source: PlaneMetricPoint
    x_px: float
    y_px: float
    x_fraction: float
    y_fraction: float
    inside_image: bool


class PlanarProjectionResponse(StrictModel):
    calibration: PlanarCalibrationResponse
    projected_points: list[ProjectedPlanePoint] = Field(
        default_factory=list,
        max_length=100,
    )


class MetricRect2D(StrictModel):
    """Axis-aligned metric footprint in the measured room coordinate system."""

    x_m: float = Field(ge=0, le=100)
    y_m: float = Field(ge=0, le=100)
    width_m: float = Field(gt=0, le=100)
    depth_m: float = Field(ge=0, le=100)


class ConstraintZone(StrictModel):
    """A measured no-placement or service zone derived from confirmed geometry."""

    label: str = Field(min_length=1, max_length=120)
    source_type: Literal[
        "room",
        "door",
        "window",
        "furniture",
        "outlet",
        "stairs",
        "walkway",
        "other",
        "clearance",
    ]
    bounds: MetricRect2D
    clearance_m: float = Field(ge=0, le=5)


class ScaleAwareTargets(StrictModel):
    """Planning envelope sized from the largest genuinely usable focal span."""

    size_class: Literal["compact", "standard", "large", "hall"]
    usable_focal_width_m: float = Field(gt=0, le=100)
    recommended_backdrop_width_m: float = Field(gt=0, le=100)
    recommended_backdrop_height_m: float = Field(gt=0, le=30)
    recommended_table_width_m: float = Field(gt=0, le=20)
    recommended_floor_decor_spread_m: float = Field(gt=0, le=100)
    backdrop_wall_coverage_fraction: float = Field(gt=0, le=1)


class ConstraintViolation(StrictModel):
    code: Literal[
        "out_of_room",
        "obstacle_collision",
        "object_collision",
        "insufficient_circulation",
        "missing_dimensions",
    ]
    message: str = Field(min_length=1, max_length=300)
    asset_id: str | None = Field(default=None, max_length=200)


class RoomConstraintRequest(StrictModel):
    space: SpaceInput
    minimum_clearance_m: float = Field(default=0.9, ge=0.9, le=5)
    objects: list[ObjectPlacement] = Field(default_factory=list, max_length=100)


class RoomConstraintResponse(StrictModel):
    status: Literal[
        "verified",
        "manual_review_required",
        "no_usable_zone",
        "violations",
    ]
    room_bounds: MetricRect2D
    largest_focal_zone: MetricRect2D | None = None
    forbidden_zones: list[ConstraintZone] = Field(default_factory=list, max_length=100)
    scale_targets: ScaleAwareTargets | None = None
    hard_constraints_ready: bool
    available_front_clearance_m: float = Field(ge=0, le=100)
    violations: list[ConstraintViolation] = Field(default_factory=list, max_length=100)
    limitations: list[str] = Field(default_factory=list, max_length=12)
