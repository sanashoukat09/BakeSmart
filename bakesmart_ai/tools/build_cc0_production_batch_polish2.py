"""Production visual-polish entrypoint for Batch-1 assets.

For the Mehndi floor arrangement this pass replaces the procedural flower-ball
heads with vetted real CC0 flower geometry/textures from Poly Haven while
preserving the corrected brass pot, true-size envelope, placement metadata and
mobile triangle budget. The approved low floral and corrected mirror are not
changed by this wrapper.
"""
from __future__ import annotations

import re
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
LEAF_PREFIXES = (
    "BS_MehndiLeaf",
    "BS_LowerLeaf",
    "BS_FinalFillLeaf",
)
STEM_PREFIXES = (
    "BS_MehndiStem_",
    "BS_FinalFillStem_",
)
AUTHORED_SUPPORT_PREFIXES = (
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


def _remove_redundant_supports() -> tuple[int, int]:
    """Reduce the old authored lattice before placing realistic flower patches."""
    removed_stems = 0
    removed_leaves = 0
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        if obj.name.startswith("BS_MehndiStem_"):
            match = re.search(r"BS_MehndiStem_(\d+)", obj.name)
            if match and int(match.group(1)) % 2 == 1:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_stems += 1
        elif obj.name.startswith("BS_MehndiLeafB_"):
            match = re.search(r"BS_MehndiLeafB_(\d+)", obj.name)
            if match and int(match.group(1)) % 2 == 0:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_leaves += 1
    bpy.context.view_layer.update()
    return removed_stems, removed_leaves


def _darken_support_materials() -> None:
    stem = base.material("BS_RealFlowerStem", (0.006, 0.030, 0.003, 1.0), roughness=0.86)
    leaf = base.material("BS_RealFlowerLeaf", (0.010, 0.060, 0.006, 1.0), roughness=0.82)
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if any(obj.name.startswith(prefix) for prefix in STEM_PREFIXES):
            obj.data.materials.clear()
            obj.data.materials.append(stem)
        elif any(obj.name.startswith(prefix) for prefix in LEAF_PREFIXES):
            obj.data.materials.clear()
            obj.data.materials.append(leaf)


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
    base.fit_exact(objects, width, depth, height, z)
    _rotate_group(objects, rotation_deg)
    _offset_group(objects, Vector(offset))
    return objects


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

    removed_flowers = _delete_prefixes(PROCEDURAL_FLOWER_PREFIXES)
    removed_stems, removed_leaves = _remove_redundant_supports()
    if removed_flowers == 0:
        raise RuntimeError("expected procedural marigold heads were not found")

    secondary = row.get("secondary_source_id", "").strip()
    tertiary = row.get("tertiary_source_id", "").strip()
    if secondary != "ph-flower-empodium" or tertiary != "ph-flower-gazania":
        raise RuntimeError(
            "real-flower marigold candidate requires ph-flower-empodium and ph-flower-gazania provenance"
        )

    # Maintain width headroom while bringing the visible depth above the
    # validator's 85% minimum (0.595 m for the 0.70 m envelope). Small rotations
    # keep the two real flower patches organic without inflating their AABB.
    _place_real_flower_patch(
        secondary,
        "CC0_Empodium",
        width=0.56,
        depth=0.55,
        height=0.34,
        z=0.38,
        rotation_deg=-6.0,
        offset=(-0.006, 0.010, 0.0),
    )

    _place_real_flower_patch(
        tertiary,
        "CC0_Gazania",
        width=0.59,
        depth=0.59,
        height=0.54,
        z=0.43,
        rotation_deg=7.0,
        offset=(0.006, -0.008, 0.0),
    )

    final.transform_authored(AUTHORED_SUPPORT_PREFIXES, sz=0.90, pivot_z=0.34)
    _darken_support_materials()

    print(
        "real-flower replacement: "
        f"removed procedural heads={removed_flowers}, "
        f"removed stems={removed_stems}, removed leaves={removed_leaves}"
    )


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
