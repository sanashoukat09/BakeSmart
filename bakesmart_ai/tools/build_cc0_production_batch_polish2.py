"""Production visual-polish entrypoint for Batch-1 assets.

For the Mehndi floor arrangement this pass replaces the procedural flower-ball
heads and their artificial support lattice with vetted real CC0 flower
geometry/textures from Poly Haven. The corrected brass pot, true-size envelope,
placement metadata and mobile triangle budget remain authoritative. The
approved low floral and corrected mirror are not changed by this wrapper.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_cc0_production_batch_final as final

base = final.base
_previous_marigold = base.build_marigold

PROCEDURAL_FLOWER_PREFIXES = (
    "BS_Marigold_",
    "BS_LowerMarigold_",
    "BS_FinalFillMarigold_",
    "BS_FinalCollarMarigold_",
)
LEGACY_SUPPORT_PREFIXES = (
    "BS_MehndiStem_",
    "BS_MehndiLeaf",
    "BS_LowerLeaf",
    "BS_FinalFillStem_",
    "BS_FinalFillLeaf",
)


def _delete_prefixes(prefixes: tuple[str, ...]) -> int:
    removed = 0
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH" and any(obj.name.startswith(prefix) for prefix in prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
    bpy.context.view_layer.update()
    return removed


def _rotate_group(objects: list[bpy.types.Object], degrees: float) -> None:
    import math

    radians = math.radians(degrees)
    for obj in objects:
        obj.rotation_euler[2] += radians
    bpy.context.view_layer.update()


def _offset_group(objects: list[bpy.types.Object], delta: Vector) -> None:
    for obj in objects:
        obj.location += delta
    bpy.context.view_layer.update()


def _place_real_flower_patch(
    source_id: str,
    prefix: str,
    width: float,
    depth: float,
    height: float,
    z: float,
    rotation_deg: float,
    offset: tuple[float, float, float],
) -> list[bpy.types.Object]:
    objects = base.import_source(source_id, prefix)
    # Preserve the provider UVs, alpha masks and PBR textures. BakeSmart only
    # performs true-size composition and the standard mobile LOD pass.
    base.fit_exact(objects, width, depth, height, z)
    _rotate_group(objects, rotation_deg)
    _offset_group(objects, Vector(offset))
    return objects


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

    # Remove the entire old procedural floral system. Keeping even part of the
    # support lattice made the otherwise realistic flower assets read as a cage
    # in front/side QA views.
    removed_flowers = _delete_prefixes(PROCEDURAL_FLOWER_PREFIXES)
    removed_supports = _delete_prefixes(LEGACY_SUPPORT_PREFIXES)
    if removed_flowers == 0 or removed_supports == 0:
        raise RuntimeError(
            "expected legacy marigold geometry was not found: "
            f"flowers={removed_flowers}, supports={removed_supports}"
        )

    secondary = row.get("secondary_source_id", "").strip()
    tertiary = row.get("tertiary_source_id", "").strip()
    if secondary != "ph-flower-empodium" or tertiary != "ph-flower-gazania":
        raise RuntimeError(
            "real-flower marigold candidate requires ph-flower-empodium and ph-flower-gazania provenance"
        )

    # A broad yellow/pale lower patch fills the pot rim and hides the imported
    # plants' base. Its lower height keeps it subordinate to the orange layer.
    _place_real_flower_patch(
        secondary,
        "CC0_Empodium",
        width=0.58,
        depth=0.58,
        height=0.38,
        z=0.34,
        rotation_deg=-5.0,
        offset=(-0.010, 0.012, 0.0),
    )

    # The orange Gazania patch is the hero layer. It overlaps the lower patch
    # closely enough to read as one bouquet while keeping the complete module
    # inside the 0.70 x 0.70 x 1.10 m production envelope.
    _place_real_flower_patch(
        tertiary,
        "CC0_Gazania",
        width=0.62,
        depth=0.61,
        height=0.61,
        z=0.35,
        rotation_deg=5.0,
        offset=(0.010, -0.010, 0.0),
    )

    print(
        "real-flower crown: "
        f"removed procedural heads={removed_flowers}, removed legacy supports={removed_supports}"
    )


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
