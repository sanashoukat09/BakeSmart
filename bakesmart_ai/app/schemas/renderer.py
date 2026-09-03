"""Stage-7 local renderer and modular review-scene contracts."""

from typing import Literal

from pydantic import Field

from app.schemas.assets import VerticalSliceCelebration
from app.schemas.design import Dimensions, StrictModel


class RendererCapabilitiesResponse(StrictModel):
    renderer_version: Literal["professional-webgl-v1"] = "professional-webgl-v1"
    local_only: Literal[True] = True
    external_runtime_dependencies: Literal[False] = False
    gltf_2_glb: Literal[True] = True
    multi_glb_modules: Literal[True] = True
    multi_node_mesh: Literal[True] = True
    pbr_metallic_roughness_factors: Literal[True] = True
    base_color_texture: Literal[True] = True
    metallic_roughness_texture: Literal[True] = True
    emissive_texture: Literal[True] = True
    normal_map_texture: Literal[False] = False
    embedded_glb_images: Literal[True] = True
    same_origin_external_images: Literal[True] = True
    object_selection: Literal[True] = True
    orbit_pan_zoom: Literal[True] = True
    planar_contact_shadow: Literal[True] = True
    metric_module_transforms: Literal[True] = True
    runtime_lod_switching: Literal[False] = False
    image_based_lighting: Literal[False] = False
    customer_production_modular_scene_ready: Literal[False] = False
    limitations: list[str] = Field(default_factory=list, max_length=12)


class ModularSceneModule(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    role: Literal["backdrop", "support", "lighting", "table", "signage"]
    instance_index: int = Field(ge=1, le=50)
    glb_url: str = Field(min_length=1, max_length=260)
    translation_m: tuple[float, float, float]
    uniform_scale: Literal[1.0] = 1.0
    dimensions: Dimensions


class VerticalSliceSceneManifestResponse(StrictModel):
    scene_version: Literal["professional-modular-review-v1"] = (
        "professional-modular-review-v1"
    )
    celebration: VerticalSliceCelebration
    status: Literal["fits", "partial", "does_not_fit"]
    review_only: Literal[True] = True
    true_size_only: Literal[True] = True
    customer_runtime_ready: Literal[False] = False
    usable_focal_width_m: float = Field(gt=0, le=100)
    requested_visual_width_m: float = Field(gt=0, le=100)
    achieved_visual_width_m: float = Field(ge=0, le=100)
    modules: list[ModularSceneModule] = Field(default_factory=list, max_length=50)
    viewer_url: str = Field(min_length=1, max_length=500)
    notes: list[str] = Field(default_factory=list, max_length=24)


class CustomerSceneModule(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    role: Literal[
        "backdrop",
        "decoration",
        "lighting",
        "signage",
    ]
    instance_index: int = Field(ge=1, le=50)
    glb_url: str = Field(min_length=1, max_length=260)
    translation_m: tuple[float, float, float]
    uniform_scale: Literal[1.0] = 1.0
    dimensions: Dimensions


class CustomerSceneManifestResponse(StrictModel):
    scene_version: Literal["customer-production-modular-v1"] = (
        "customer-production-modular-v1"
    )
    design_id: str = Field(pattern=r"^design-[0-9a-f]{20}$")
    units: Literal["metres"] = "metres"
    production_module_count: int = Field(ge=0, le=50)
    procedural_glb_url: str = Field(min_length=1, max_length=260)
    modules: list[CustomerSceneModule] = Field(default_factory=list, max_length=50)
    procedural_fallback_catalog_ids: list[str] = Field(default_factory=list, max_length=50)
    notes: list[str] = Field(default_factory=list, max_length=20)
