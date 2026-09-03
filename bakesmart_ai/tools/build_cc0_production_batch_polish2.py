"""Second visual-polish pass for the Batch-1 marigold candidate.

The first corrected marigold already sits close to the 26k mobile triangle
budget.  This pass therefore works by reusing/scaling existing flower geometry,
forcing reliable mobile-safe materials directly onto meshes, and removing a
subset of redundant long stems.  It does not alter the approved low floral or
the corrected welcome mirror.
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

FLOWER_PREFIXES = (
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


def _scale_existing_meshes(prefixes: tuple[str, ...], factor: Vector) -> int:
    changed = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not any(obj.name.startswith(prefix) for prefix in prefixes):
            continue
        obj.scale = Vector((obj.scale.x * factor.x, obj.scale.y * factor.y, obj.scale.z * factor.z))
        changed += 1
    bpy.context.view_layer.update()
    return changed


def _force_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        for index in range(len(obj.data.materials)):
            obj.data.materials[index] = mat


def _flower_group_index(name: str) -> int:
    match = re.search(r"Marigold_(\d+)", name)
    if match:
        return int(match.group(1))
    # Final fill/collar names contain the same numbered token after Marigold_.
    digits = re.findall(r"\d+", name)
    return int(digits[0]) if digits else 0


def _remove_redundant_long_stems() -> int:
    """Remove alternate original long stems to stop the cage-like silhouette."""
    removed = 0
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.name.startswith("BS_MehndiStem_"):
            continue
        match = re.search(r"BS_MehndiStem_(\d+)", obj.name)
        if match and int(match.group(1)) % 2 == 1:
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
    bpy.context.view_layer.update()
    return removed


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

    flower_count = _scale_existing_meshes(
        FLOWER_PREFIXES,
        Vector((1.24, 1.24, 1.16)),
    )
    leaf_count = _scale_existing_meshes(
        LEAF_PREFIXES,
        Vector((1.22, 1.22, 1.08)),
    )
    if flower_count == 0 or leaf_count == 0:
        raise RuntimeError(
            f"expected existing marigold geometry was not found: flowers={flower_count}, leaves={leaf_count}"
        )

    # Use explicit new materials and assign them directly to every mesh.  This
    # avoids Blender's .001/.002 material-name reuse and keeps the exported GLB
    # consistent under headless rebuilds and mobile PBR viewers.
    orange = base.material("BS_PolishOrange", (0.42, 0.012, 0.001, 1.0), roughness=0.58)
    saffron = base.material("BS_PolishSaffron", (0.60, 0.065, 0.002, 1.0), roughness=0.57)
    yellow = base.material("BS_PolishYellow", (0.72, 0.36, 0.006, 1.0), roughness=0.60)
    deep_stem = base.material("BS_PolishStem", (0.004, 0.026, 0.001, 1.0), roughness=0.80)
    deep_leaf = base.material("BS_PolishLeaf", (0.008, 0.060, 0.003, 1.0), roughness=0.77)

    assigned_flowers = 0
    assigned_stems = 0
    assigned_leaves = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if any(obj.name.startswith(prefix) for prefix in FLOWER_PREFIXES):
            group_index = _flower_group_index(obj.name)
            if "_Core" in obj.name:
                chosen = saffron
            elif group_index % 4 == 0:
                chosen = yellow
            else:
                chosen = orange
            _force_material(obj, chosen)
            assigned_flowers += 1
        elif any(obj.name.startswith(prefix) for prefix in STEM_PREFIXES):
            _force_material(obj, deep_stem)
            assigned_stems += 1
        elif any(obj.name.startswith(prefix) for prefix in LEAF_PREFIXES):
            _force_material(obj, deep_leaf)
            assigned_leaves += 1

    removed_stems = _remove_redundant_long_stems()
    if assigned_flowers == 0 or assigned_stems == 0 or assigned_leaves == 0 or removed_stems == 0:
        raise RuntimeError(
            "marigold polish assignment failed: "
            f"flowers={assigned_flowers}, stems={assigned_stems}, leaves={assigned_leaves}, removed={removed_stems}"
        )


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
