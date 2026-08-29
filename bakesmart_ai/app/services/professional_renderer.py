"""Stage-7 truthful capabilities and review-only modular scene assembly."""

from __future__ import annotations

from urllib.parse import urlencode

from app.schemas.assets import VerticalSliceCompositionRequest
from app.schemas.design import Dimensions
from app.schemas.renderer import (
    ModularSceneModule,
    RendererCapabilitiesResponse,
    VerticalSliceSceneManifestResponse,
)
from app.services.vertical_slice import vertical_slice_service


_RENDERER_LIMITATIONS = [
    "The renderer implements local GLB 2.0 multi-module assembly and material-aware WebGL without a hosted rendering service.",
    "It supports PBR metallic/roughness factors plus base-color, metallic-roughness, and emissive textures when GLBs provide UV coordinates.",
    "Normal-map tangent-space shading and image-based environment lighting are not implemented yet.",
    "Contact shadows are a deterministic planar approximation, not ray-traced shadows.",
    "Runtime LOD switching is not enabled until reviewed LOD1/LOD2 production files exist.",
    "The Stage-6 Birthday/Wedding/Mehndi assets remain review-only low-poly prototypes and are not customer production assets.",
    "Customer modular rendering remains gated on production-ready, rights-cleared assets even though the renderer can assemble multiple GLBs.",
]


def renderer_capabilities() -> RendererCapabilitiesResponse:
    return RendererCapabilitiesResponse(limitations=list(_RENDERER_LIMITATIONS))


def build_vertical_slice_scene(
    request: VerticalSliceCompositionRequest,
) -> VerticalSliceSceneManifestResponse:
    """Turn the true-size Stage-6 composition into a browser-loadable module list."""

    composition = vertical_slice_service.compose(request)
    modules: list[ModularSceneModule] = []
    notes = list(composition.notes)

    for placement in composition.placements:
        vertical_slice_service.review_glb(placement.asset_id)
        modules.append(
            ModularSceneModule(
                asset_id=placement.asset_id,
                catalog_id=placement.catalog_id,
                role=placement.role,
                instance_index=placement.instance_index,
                glb_url=f"/api/v1/assets/3d/review/{placement.asset_id}.glb",
                translation_m=(
                    placement.x_center_m,
                    placement.base_height_m,
                    placement.depth_from_focal_wall_m,
                ),
                uniform_scale=1.0,
                dimensions=Dimensions(
                    width_m=placement.true_width_m,
                    depth_m=placement.true_depth_m,
                    height_m=placement.true_height_m,
                ),
            )
        )

    if modules:
        notes.append(
            "Stage 7 assembles each review GLB as an independent selectable object at uniform scale 1.0; metre dimensions are not normalized per asset."
        )
    else:
        notes.append(
            "No module is emitted when the true-size primary structure cannot fit the confirmed usable focal span."
        )

    query = urlencode(
        {
            "usable": f"{request.usable_focal_width_m:.3f}",
            "target": f"{request.target_visual_width_m:.3f}",
            "lighting": "true" if request.include_lighting else "false",
        }
    )
    viewer_url = f"/viewer/vertical-slice/{request.celebration}?{query}"

    return VerticalSliceSceneManifestResponse(
        celebration=request.celebration,
        status=composition.status,
        usable_focal_width_m=composition.usable_focal_width_m,
        requested_visual_width_m=composition.requested_visual_width_m,
        achieved_visual_width_m=composition.achieved_visual_width_m,
        modules=modules,
        viewer_url=viewer_url,
        notes=list(dict.fromkeys(notes)),
    )
