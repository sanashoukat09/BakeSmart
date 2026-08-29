"""Production 3D asset contracts for BakeSmart's local asset pipeline."""

from typing import Literal

from pydantic import Field

from app.schemas.design import Dimensions, StrictModel


class MaterialProfileRecord(StrictModel):
    profile_id: str = Field(pattern=r"^mat-[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=120)
    metallic: float = Field(ge=0, le=1)
    roughness: float = Field(ge=0, le=1)
    alpha_mode: Literal["OPAQUE", "MASK", "BLEND"]
    double_sided: bool
    pbr_required: bool
    base_color_texture_required: bool
    orm_texture_required: bool
    emissive_texture_allowed: bool
    texture_max_px: int = Field(ge=256, le=4096)
    notes: str = Field(min_length=1, max_length=500)


class ProductionAssetRecord(StrictModel):
    """One true-size modular GLB requirement mapped to a real catalogue item."""

    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    glb_path: str = Field(min_length=1, max_length=240)
    blend_source_path: str = Field(min_length=1, max_length=240)
    dimensions: Dimensions
    anchor_type: Literal[
        "floor_center",
        "wall_floor_center",
        "wall_center",
        "surface_center",
        "overhead_center",
    ]
    scaling_policy: Literal[
        "fixed_true_size",
        "repeat_x",
        "modular_cluster",
    ]
    repeat_axis: Literal["none", "x", "y", "z"]
    min_uniform_scale: float = Field(ge=0.5, le=2)
    max_uniform_scale: float = Field(ge=0.5, le=2)
    collision_padding_m: float = Field(ge=0, le=1)
    material_profile_id: str = Field(pattern=r"^mat-[a-z0-9]+(?:-[a-z0-9]+)*$")
    lod0_triangle_budget: int = Field(gt=0, le=200_000)
    lod1_triangle_budget: int = Field(gt=0, le=100_000)
    lod2_triangle_budget: int = Field(gt=0, le=50_000)
    texture_max_px: int = Field(ge=256, le=4096)
    source_license_status: Literal[
        "pending_rights_review",
        "original_confirmed",
        "cc0_confirmed",
        "commercial_redistribution_confirmed",
    ]
    redistribution_allowed: bool
    production_status: Literal[
        "planned",
        "in_authoring",
        "geometry_review",
        "material_review",
        "production_ready",
        "rejected",
    ]
    renderable: bool


class ProductionAssetLibrarySummary(StrictModel):
    manifest_version: Literal["production-assets-v1"] = "production-assets-v1"
    total_asset_requirements: int = Field(ge=0)
    real_catalog_item_count: int = Field(ge=0)
    mapped_catalog_item_count: int = Field(ge=0)
    material_profile_count: int = Field(ge=0)
    production_ready_count: int = Field(ge=0)
    missing_glb_count: int = Field(ge=0)
    pending_rights_review_count: int = Field(ge=0)
    target_min_assets: Literal[80] = 80
    target_max_assets: Literal[120] = 120
    library_target_met: bool
    runtime_external_glb_assembly_ready: Literal[False] = False
    pbr_runtime_renderer_ready: Literal[False] = False


class ProductionAssetCatalogResponse(StrictModel):
    summary: ProductionAssetLibrarySummary
    assets: list[ProductionAssetRecord] = Field(default_factory=list, max_length=200)
    material_profiles: list[MaterialProfileRecord] = Field(
        default_factory=list,
        max_length=50,
    )
    limitations: list[str] = Field(default_factory=list, max_length=12)


class ProductionAssetValidationRequest(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProductionAssetValidationResponse(StrictModel):
    asset_id: str
    catalog_id: str
    status: Literal[
        "missing_glb",
        "not_approved",
        "invalid_glb",
        "ready",
    ]
    glb_path: str
    file_size_bytes: int | None = Field(default=None, ge=0)
    triangle_count: int | None = Field(default=None, ge=0)
    checks: list[str] = Field(default_factory=list, max_length=30)
    errors: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    renderable: bool


VerticalSliceCelebration = Literal[
    "birthday",
    "wedding",
    "south_asian_mehndi",
]


class VerticalSliceAssetState(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    role: Literal["backdrop", "support", "lighting", "table", "signage"]
    glb_present: bool
    structurally_valid: bool
    production_status: Literal[
        "planned",
        "in_authoring",
        "geometry_review",
        "material_review",
        "production_ready",
        "rejected",
    ]
    customer_renderable: bool
    review_glb_url: str | None = None


class VerticalSliceCelebrationState(StrictModel):
    celebration: VerticalSliceCelebration
    display_name: str = Field(min_length=1, max_length=80)
    required_asset_count: int = Field(ge=1, le=20)
    present_glb_count: int = Field(ge=0, le=20)
    structurally_valid_count: int = Field(ge=0, le=20)
    production_ready_count: int = Field(ge=0, le=20)
    geometry_slice_complete: bool
    customer_slice_ready: bool
    assets: list[VerticalSliceAssetState] = Field(min_length=1, max_length=20)
    blockers: list[str] = Field(default_factory=list, max_length=12)


class VerticalSliceSummaryResponse(StrictModel):
    slice_version: Literal["professional-vertical-slice-v1"] = (
        "professional-vertical-slice-v1"
    )
    geometry_review_assets_present: bool
    customer_runtime_ready: bool
    celebrations: list[VerticalSliceCelebrationState] = Field(
        min_length=3,
        max_length=3,
    )
    limitations: list[str] = Field(default_factory=list, max_length=12)


class VerticalSliceCompositionRequest(StrictModel):
    celebration: VerticalSliceCelebration
    usable_focal_width_m: float = Field(gt=0, le=100)
    target_visual_width_m: float = Field(gt=0, le=100)
    include_lighting: bool = True


class VerticalSlicePlacement(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    role: Literal["backdrop", "support", "lighting", "table", "signage"]
    instance_index: int = Field(ge=1, le=50)
    x_center_m: float = Field(ge=-100, le=100)
    depth_from_focal_wall_m: float = Field(ge=0, le=100)
    base_height_m: float = Field(ge=0, le=30)
    uniform_scale: Literal[1.0] = 1.0
    true_width_m: float = Field(gt=0, le=100)
    true_depth_m: float = Field(gt=0, le=100)
    true_height_m: float = Field(gt=0, le=30)


class VerticalSliceCompositionResponse(StrictModel):
    celebration: VerticalSliceCelebration
    status: Literal["fits", "partial", "does_not_fit"]
    usable_focal_width_m: float = Field(gt=0, le=100)
    requested_visual_width_m: float = Field(gt=0, le=100)
    achieved_visual_width_m: float = Field(ge=0, le=100)
    true_size_only: Literal[True] = True
    review_only: Literal[True] = True
    placements: list[VerticalSlicePlacement] = Field(default_factory=list, max_length=50)
    notes: list[str] = Field(default_factory=list, max_length=20)
