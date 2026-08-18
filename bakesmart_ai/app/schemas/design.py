from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AreaType(str, Enum):
    WALL = "wall"
    ROOM = "room"
    TABLE = "table"
    OUTDOOR_AREA = "outdoor_area"


class VenueType(str, Enum):
    HALL = "hall"
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    RESTAURANT = "restaurant"
    GARDEN = "garden"
    ROOFTOP = "rooftop"
    OTHER = "other"


class EnvironmentType(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    SEMI_OUTDOOR = "semi_outdoor"


class EventType(str, Enum):
    BIRTHDAY = "birthday"
    WEDDING = "wedding"
    KIDS_BIRTHDAY = "kids_birthday"
    BABY_SHOWER = "baby_shower"
    ENGAGEMENT = "engagement"
    CORPORATE = "corporate"
    ANNIVERSARY = "anniversary"
    OTHER = "other"


class ObstacleType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    FURNITURE = "furniture"
    OUTLET = "outlet"
    STAIRS = "stairs"
    WALKWAY = "walkway"
    OTHER = "other"


class PhotoAngle(str, Enum):
    WIDE = "wide"
    SECOND_ANGLE = "second_angle"


class PhotoQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CakeShape(str, Enum):
    ROUND = "round"
    SQUARE = "square"
    RECTANGLE = "rectangle"
    HEART = "heart"
    CUSTOM = "custom"


class Dimensions(StrictModel):
    width_m: float = Field(gt=0, le=100)
    depth_m: float | None = Field(default=None, gt=0, le=100)
    height_m: float = Field(gt=0, le=30)


class Position3D(StrictModel):
    x_m: float = Field(ge=0, le=100)
    y_m: float = Field(ge=0, le=100)
    z_m: float = Field(ge=0, le=30)


class ObstacleInput(StrictModel):
    obstacle_type: ObstacleType
    label: str | None = Field(default=None, max_length=80)
    position: Position3D
    dimensions: Dimensions


class VenuePhotoEvidence(StrictModel):
    photo_id: str = Field(pattern=r"^venue-photo-[a-f0-9]{20}$")
    angle: PhotoAngle
    pixel_width: int = Field(ge=1, le=20_000)
    pixel_height: int = Field(ge=1, le=20_000)
    file_size_bytes: int = Field(ge=1, le=8_000_000)
    quality: PhotoQuality
    brightness_score: float = Field(ge=0, le=1)
    contrast_score: float = Field(ge=0, le=1)
    sharpness_score: float = Field(ge=0, le=1)
    observations: list[str] = Field(default_factory=list, max_length=12)


class SpaceInput(StrictModel):
    area_type: AreaType
    venue_type: VenueType
    environment: EnvironmentType
    dimensions: Dimensions
    obstacles: list[ObstacleInput] = Field(default_factory=list, max_length=50)
    obstacle_map_confirmed: bool = False
    known_reference_m: float | None = Field(default=None, gt=0, le=20)
    photo_references: list[str] = Field(default_factory=list, max_length=6)
    photo_evidence: list[VenuePhotoEvidence] = Field(
        default_factory=list,
        max_length=2,
    )

    @model_validator(mode="after")
    def require_depth_for_area(self) -> "SpaceInput":
        depth_required = {
            AreaType.ROOM,
            AreaType.TABLE,
            AreaType.OUTDOOR_AREA,
        }
        if self.area_type in depth_required and self.dimensions.depth_m is None:
            raise ValueError(
                f"depth_m is required for area_type '{self.area_type.value}'"
            )
        angles = [photo.angle for photo in self.photo_evidence]
        if len(angles) != len(set(angles)):
            raise ValueError("photo_evidence may contain only one photo per angle")
        for obstacle in self.obstacles:
            label = obstacle.label or obstacle.obstacle_type.value
            if (
                obstacle.position.x_m + obstacle.dimensions.width_m
                > self.dimensions.width_m
            ):
                raise ValueError(f"obstacle '{label}' exceeds the measured width")
            obstacle_depth = obstacle.dimensions.depth_m or 0.0
            if (
                self.dimensions.depth_m is not None
                and obstacle.position.y_m + obstacle_depth > self.dimensions.depth_m
            ):
                raise ValueError(f"obstacle '{label}' exceeds the measured depth")
            if (
                obstacle.position.z_m + obstacle.dimensions.height_m
                > self.dimensions.height_m
            ):
                raise ValueError(f"obstacle '{label}' exceeds the measured height")
        return self


class CakeInput(StrictModel):
    cake_image_reference: str = Field(min_length=1, max_length=2048)
    shape: CakeShape
    tiers: int = Field(ge=1, le=10)
    servings_required: int = Field(ge=1, le=2000)
    diameter_m: float | None = Field(default=None, gt=0, le=3)
    width_m: float | None = Field(default=None, gt=0, le=3)
    depth_m: float | None = Field(default=None, gt=0, le=3)
    height_m: float = Field(gt=0, le=3)

    @model_validator(mode="after")
    def require_shape_dimensions(self) -> "CakeInput":
        if self.shape == CakeShape.ROUND and self.diameter_m is None:
            raise ValueError("diameter_m is required for a round cake")
        if self.shape != CakeShape.ROUND and (
            self.width_m is None or self.depth_m is None
        ):
            raise ValueError("width_m and depth_m are required for a non-round cake")
        return self


class EventInput(StrictModel):
    event_type: EventType
    guest_count: int = Field(ge=1, le=10000)
    theme_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    preferred_colors: list[str] = Field(default_factory=list, max_length=8)
    excluded_colors: list[str] = Field(default_factory=list, max_length=8)
    required_decor_categories: list[str] = Field(default_factory=list, max_length=20)
    excluded_decor_categories: list[str] = Field(default_factory=list, max_length=20)


class DesignRequest(StrictModel):
    customer_id: str = Field(min_length=1, max_length=128)
    space: SpaceInput
    event: EventInput
    cake: CakeInput
    decoration_budget_pkr: int = Field(gt=0, le=100_000_000)
    minimum_clearance_m: float = Field(default=0.9, ge=0.9, le=5)


class Rotation3D(StrictModel):
    x_degrees: float = Field(default=0, ge=-360, le=360)
    y_degrees: float = Field(default=0, ge=-360, le=360)
    z_degrees: float = Field(default=0, ge=-360, le=360)


class ObjectPlacement(StrictModel):
    asset_id: str
    role: Literal[
        "cake",
        "cake_table",
        "backdrop",
        "decoration",
        "lighting",
        "signage",
    ]
    catalog_id: str | None = None
    position: Position3D
    rotation: Rotation3D = Field(default_factory=Rotation3D)
    scale: float = Field(default=1, gt=0, le=20)
    dimensions: Dimensions | None = None


class DecorRecommendation(StrictModel):
    catalog_id: str
    name: str
    category: str
    quantity: int = Field(ge=1)
    unit_cost_pkr: int = Field(ge=0)
    placements: list[ObjectPlacement] = Field(min_length=1)


class CakePlacement(StrictModel):
    catalog_id: str | None = None
    source_image_reference: str
    shape: CakeShape
    tiers: int = Field(ge=1, le=10)
    placement: ObjectPlacement
    servings: int = Field(ge=1)
    estimated_cost_pkr: int = Field(ge=0)


class CostBreakdown(StrictModel):
    decoration_cost_pkr: int = Field(ge=0)
    cake_cost_pkr: int = Field(ge=0)
    total_cost_pkr: int = Field(ge=0)
    budget_pkr: int = Field(gt=0)
    remaining_budget_pkr: int = Field(ge=0)
    budget_scope: Literal["decorations_only"] = "decorations_only"
    pricing_basis: Literal["synthetic_planning_estimate_not_vendor_quote"]


class ModelSignal(StrictModel):
    label: str
    confidence: float = Field(ge=0, le=1)


class VenuePhotoAnalysisRequest(StrictModel):
    file_name: str = Field(min_length=1, max_length=180)
    media_type: Literal["image/jpeg", "image/png"]
    image_base64: str = Field(min_length=4, max_length=11_000_000)
    angle: PhotoAngle


class VenuePhotoAnalysis(StrictModel):
    photo_id: str = Field(pattern=r"^venue-photo-[a-f0-9]{20}$")
    angle: PhotoAngle
    pixel_width: int = Field(ge=1, le=20_000)
    pixel_height: int = Field(ge=1, le=20_000)
    file_size_bytes: int = Field(ge=1, le=8_000_000)
    orientation: Literal["landscape", "portrait", "square"]
    quality: PhotoQuality
    brightness_score: float = Field(ge=0, le=1)
    contrast_score: float = Field(ge=0, le=1)
    sharpness_score: float = Field(ge=0, le=1)
    horizontal_structure_score: float = Field(ge=0, le=1)
    observations: list[str]
    limitations: list[str]
    exact_scale_available: Literal[False] = False
    persisted: Literal[False] = False


class VenueAssessment(StrictModel):
    photo_count: int = Field(ge=0, le=2)
    evidence_confidence: Literal["high", "medium", "low"]
    placement_status: Literal["clearance_verified", "manual_review_required"]
    scale_source: Literal[
        "user_confirmed_measurements",
        "unverified",
    ]
    selected_focal_center_x_m: float = Field(ge=0, le=100)
    available_front_clearance_m: float = Field(ge=0, le=100)
    minimum_clearance_m: float = Field(ge=0.9, le=5)
    obstacle_count: int = Field(ge=0, le=50)
    obstacle_map_confirmed: bool
    blocking_obstacles: list[str]
    observed_facts: list[str]
    assumptions: list[str]


class PreviewAvailability(StrictModel):
    interactive_3d_ready: bool
    viewer_3d_url: str | None = None
    viewer_label: Literal["Open Interactive 3D View"] | None = None
    scene_glb_url: str | None = None
    ar_supported: bool | None = None
    ar_url: str | None = None
    fallback_label: Literal["Concept preview—not to scale"] | None = None


class SceneSpecification(StrictModel):
    units: Literal["metres"] = "metres"
    space: SpaceInput
    objects: list[ObjectPlacement]
    minimum_clearance_m: float = Field(ge=0.9)
    concept_not_to_scale: bool
    layout_strategy: str
    asset_status: Literal[
        "catalog_references_require_3d_asset_creation",
        "generated_procedural_glb",
    ]
    layers: list[
        Literal[
            "cake_and_baked_items",
            "dessert_table",
            "decorations",
            "backdrop",
            "lighting",
        ]
    ]


class RecommendationResponse(StrictModel):
    design_id: str
    created_at: datetime
    model_version: str
    model_signals: dict[Literal["theme", "cake", "decor", "layout"], ModelSignal]
    selected_theme_id: str
    decorations: list[DecorRecommendation]
    cake: CakePlacement
    costs: CostBreakdown
    venue_assessment: VenueAssessment
    scene: SceneSpecification
    preview: PreviewAvailability
    warnings: list[str] = Field(default_factory=list)


class ValidationResponse(StrictModel):
    valid: Literal[True] = True
    normalized_request: DesignRequest
    warnings: list[str] = Field(default_factory=list)


class CapabilitiesResponse(StrictModel):
    area_types: list[str]
    venue_types: list[str]
    environment_types: list[str]
    event_types: list[str]
    canonical_units: Literal["metres"]
    currency: Literal["PKR"]
    model_ready: bool


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    version: str
    model_status: Literal["not_trained", "ready", "error"]
