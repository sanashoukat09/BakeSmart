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


def _offset_group(objects: list[bpy.types.Object], delta: Vector) -> None:
    for obj in objects:
        obj.location += delta
    bpy.context.view_layer.update()


def _join_and_bake(objects: list[bpy.types.Object], name: str) -> list[bpy.types.Object]:
    """Join a provider plant into one mesh while preserving materials and UVs.

    Poly Haven botanical glTFs can contain several independently rotated mesh
    pieces. Joining them and applying rotation/scale converts those transforms
    into mesh coordinates, so the standard BakeSmart exact fitter can enforce a
    predictable world-space AABB. Blender's join operation retains material
    slots, texture-node links and UV layers used by the source PBR asset.
    """
    if not objects:
        raise RuntimeError(f"cannot join empty botanical patch {name}")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    if joined is None or joined.type != "MESH":
        raise RuntimeError(f"failed to join botanical patch {name}")
    joined.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.view_layer.update()
    return [joined]


def _verify_exact_bounds(
    objects: list[bpy.types.Object],
    width: float,
    depth: float,
    height: float,
    tolerance: float = 0.003,
) -> None:
    minimum, maximum = base.mesh_bounds(objects)
    actual = maximum - minimum
    targets = (width, depth, height)
    for index, target in enumerate(targets):
        if abs(actual[index] - target) > tolerance:
            raise RuntimeError(
                f"real flower exact fit failed on axis {index}: actual={actual[index]:.4f}, target={target:.4f}"
            )


def _place_real_flower_patch(
    source_id: str,
    prefix: str,
    width: float,
    depth: float,
    height: float,
    z: float,
    offset: tuple[float, float, float],
) -> list[bpy.types.Object]:
    imported = base.import_source(source_id, prefix)
    objects = _join_and_bake(imported, prefix + "_Patch")

    # With provider transforms baked into one mesh, the standard true-size fit
    # is deterministic and does not distort the source textures/materials.
    base.fit_exact(objects, width, depth, height, z)
    bpy.ops.object.select_all(action="DESELECT")
    objects[0].select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    _verify_exact_bounds(objects, width, depth, height)

    _offset_group(objects, Vector(offset))
    return objects


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

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

    # Broad lower patch fills the pot rim while remaining subordinate to the
    # orange Gazania hero layer.
    _place_real_flower_patch(
        secondary,
        "CC0_Empodium",
        width=0.58,
        depth=0.58,
        height=0.38,
        z=0.34,
        offset=(-0.010, 0.012, 0.0),
    )

    # Hero layer reaches 0.96 m overall with the pot: above the 0.935 m minimum
    # and below the 1.12 m maximum installation tolerance.
    _place_real_flower_patch(
        tertiary,
        "CC0_Gazania",
        width=0.62,
        depth=0.61,
        height=0.61,
        z=0.35,
        offset=(0.010, -0.010, 0.0),
    )

    print(
        "real-flower crown: "
        f"removed procedural heads={removed_flowers}, removed legacy supports={removed_supports}"
    )


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
