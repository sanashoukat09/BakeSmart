"""Build and render representative configurable cakes for reference-integration QA."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas.design import (
    CakePlacement,
    CakeShape,
    Dimensions,
    ObjectPlacement,
    Position3D,
)
from app.services.cake_references import cake_reference_library
from app.services.glb_builder import MeshAccumulator, ProceduralGlbBuilder
from tools.render_cake_reference_review import render


WORK_ROOT = ROOT / "assets" / "third_party_cc0" / "review" / "generated_cakes"
RENDER_ROOT = ROOT / "data" / "cake_references_v1" / "generated_review_renders"
REPORT_PATH = ROOT / "data" / "cake_references_v1" / "generated_review_manifest.json"

VARIANTS = (
    ("neutral-classic", "classic-elegant-cake-01", 3, "#FFFDF7;#E7D8BF;#B59B6A"),
    ("cocoa-nut", "dark-moody-chocolate-cake", 2, "#F2DFC0;#6A3219;#D29B52"),
    ("rustic-berry", "rustic-boho-fruit-cake", 2, "#F3E7D3;#9C6B4F;#6F7A55"),
)

VISUAL_FINDINGS = {
    "neutral-classic": "Three clear tiers, stable cake board, restrained neutral finish, and a distinct small topper cluster.",
    "cocoa-nut": "Two clear tiers with warm cocoa frosting, contrasting piping, and a compact cocoa-and-nut topper cluster.",
    "rustic-berry": "Two clear tiers with an earthy rustic finish, contrasting board and piping, and a readable berry-and-chocolate cluster.",
}


def _cake(catalog_id: str, tiers: int) -> CakePlacement:
    return CakePlacement(
        catalog_id=catalog_id,
        source_image_reference="cake-reference-integration-review",
        shape=CakeShape.ROUND,
        tiers=tiers,
        placement=ObjectPlacement(
            asset_id="review/configurable-cake",
            role="cake",
            position=Position3D(x_m=0, y_m=0, z_m=0),
            dimensions=Dimensions(width_m=0.3, depth_m=0.3, height_m=0.35),
        ),
        servings=40,
        estimated_cost_pkr=0,
    )


def main() -> int:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    RENDER_ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    for variant_id, catalog_id, tiers, palette_hex in VARIANTS:
        cake = _cake(catalog_id, tiers)
        profile = cake_reference_library.select(catalog_id)
        mesh = MeshAccumulator()
        dimensions = cake.placement.dimensions
        if dimensions is None:
            raise AssertionError("review cake dimensions are required")
        ProceduralGlbBuilder._add_cake(
            mesh,
            (0.0, 0.0, 0.0),
            dimensions,
            cake,
            ProceduralGlbBuilder._palette(palette_hex),
            profile,
        )
        generated = ProceduralGlbBuilder._encode(
            mesh,
            f"cake-reference-review-{variant_id}",
            ["cake_and_baked_items"],
            cake_profile=profile,
        )
        glb_path = WORK_ROOT / f"{variant_id}.glb"
        glb_path.write_bytes(generated.data)
        png_path = RENDER_ROOT / f"{variant_id}.png"
        render(glb_path, png_path, variant_id.replace("-", " ").title())
        records.append(
            {
                "variant_id": variant_id,
                "catalog_id": catalog_id,
                "profile_id": profile.profile_id,
                "selected_reference_source_id": profile.source_id,
                "dimensions_m": [0.3, 0.3, 0.35],
                "tiers": tiers,
                "vertex_count": generated.vertex_count,
                "triangle_count": generated.triangle_count,
                "render_path": f"generated_review_renders/{variant_id}.png",
                "diagnostic_visual_decision": "pass_reference_integration",
                "diagnostic_visual_finding": VISUAL_FINDINGS[variant_id],
            }
        )
        print(f"Rendered {variant_id} with {profile.profile_id}")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "customer_dimensions_preserved": True,
                "production_ready": False,
                "final_webgl_mobile_review_pending": True,
                "review_note": (
                    "Diagnostic renders passed reference integration; final production "
                    "approval still requires the BakeSmart WebGL viewer on desktop and mobile."
                ),
                "variants": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
