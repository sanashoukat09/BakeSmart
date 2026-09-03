"""Final visual-polish pass for the Batch-1 marigold candidate.

The corrected marigold already sits close to the 26k mobile triangle budget.
This pass therefore improves density and colour without adding geometry: it
reuses/scales existing flower heads, compacts the authored crown, removes
redundant stems/leaves, and forces low-specular saturated mobile-safe PBR
materials directly onto the remaining meshes. It does not alter the approved
low floral or corrected welcome mirror.
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
AUTHORED_PREFIXES = (
    "BS_Mehndi",
    "BS_Marigold",
    "BS_Lower",
    "BS_FinalFill",
    "BS_FinalCollar",
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


def _make_matte(mat: bpy.types.Material) -> None:
    """Reduce white specular wash so marigold hues stay saturated in QA/mobile."""
    if not mat.use_nodes:
        return
    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.22
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.22
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.0


def _flower_group_index(name: str) -> int:
    match = re.search(r"Marigold_(\d+)", name)
    if match:
        return int(match.group(1))
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


def _remove_redundant_secondary_leaves() -> int:
    """Thin the rigid leaf lattice while preserving broad visual foliage."""
    removed = 0
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.name.startswith("BS_MehndiLeafB_"):
            continue
        match = re.search(r"BS_MehndiLeafB_(\d+)", obj.name)
        if match and int(match.group(1)) % 2 == 0:
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
    bpy.context.view_layer.update()
    return removed


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

    # Make existing heads visibly fuller instead of adding more polygons. The
    # current crown has enough envelope headroom for this increase.
    flower_count = _scale_existing_meshes(
        FLOWER_PREFIXES,
        Vector((1.42, 1.42, 1.25)),
    )
    # Slightly reduce the earlier oversized foliage so the composition reads as
    # flowers first, while still masking support stems at normal mobile distance.
    leaf_count = _scale_existing_meshes(
        LEAF_PREFIXES,
        Vector((1.10, 1.10, 1.04)),
    )
    if flower_count == 0 or leaf_count == 0:
        raise RuntimeError(
            f"expected existing marigold geometry was not found: flowers={flower_count}, leaves={leaf_count}"
        )

    # Compact the full authored arrangement vertically around the pot shoulder.
    # This keeps the flower/stem connections intact while removing the sparse,
    # tower-like upper silhouette. The resulting height still fills >85% of the
    # 1.10 m production envelope required by the structural validator.
    final.transform_authored(AUTHORED_PREFIXES, sz=0.92, pivot_z=0.34)

    # Use sRGB-targeted linear ratios with substantially more green so orange does
    # not drift toward coral/peach under the QA renderer. Low specular response
    # preserves saturation and keeps the three flower colours distinct.
    orange = base.material("BS_PolishOrange", (0.90, 0.250, 0.0020, 1.0), roughness=0.72)
    saffron = base.material("BS_PolishSaffron", (1.00, 0.430, 0.0040, 1.0), roughness=0.70)
    yellow = base.material("BS_PolishYellow", (1.00, 0.700, 0.0200, 1.0), roughness=0.74)
    deep_stem = base.material("BS_PolishStem", (0.0004, 0.0035, 0.0002, 1.0), roughness=0.90)
    deep_leaf = base.material("BS_PolishLeaf", (0.0015, 0.012, 0.0007, 1.0), roughness=0.86)
    for mat in (orange, saffron, yellow, deep_stem, deep_leaf):
        _make_matte(mat)

    assigned_flowers = 0
    assigned_stems = 0
    assigned_leaves = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        material_names = " ".join(mat.name.lower() for mat in obj.data.materials if mat is not None)
        if any(obj.name.startswith(prefix) for prefix in FLOWER_PREFIXES) or "marigold" in material_names:
            group_index = _flower_group_index(obj.name)
            if "_Core" in obj.name:
                chosen = saffron
            elif group_index % 5 == 0:
                chosen = yellow
            elif group_index % 3 == 0:
                chosen = saffron
            else:
                chosen = orange
            _force_material(obj, chosen)
            assigned_flowers += 1
        elif any(obj.name.startswith(prefix) for prefix in STEM_PREFIXES) or "stem" in material_names:
            _force_material(obj, deep_stem)
            assigned_stems += 1
        elif any(obj.name.startswith(prefix) for prefix in LEAF_PREFIXES) or "leaf" in material_names:
            _force_material(obj, deep_leaf)
            assigned_leaves += 1

    removed_stems = _remove_redundant_long_stems()
    removed_leaves = _remove_redundant_secondary_leaves()
    if (
        assigned_flowers == 0
        or assigned_stems == 0
        or assigned_leaves == 0
        or removed_stems == 0
        or removed_leaves == 0
    ):
        raise RuntimeError(
            "marigold polish assignment failed: "
            f"flowers={assigned_flowers}, stems={assigned_stems}, leaves={assigned_leaves}, "
            f"removed_stems={removed_stems}, removed_leaves={removed_leaves}"
        )


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
