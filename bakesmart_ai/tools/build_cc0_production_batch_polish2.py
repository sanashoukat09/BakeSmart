"""Second visual-polish pass for the Batch-1 marigold candidate.

This pass intentionally adds *no new mesh geometry*.  The first corrected
marigold already consumes almost all of its 26k-triangle mobile budget, so this
module improves the visual result by enlarging existing flower/leaf volumes and
rebalancing materials only.  The approved low floral and corrected mirror are
left exactly as supplied by ``build_cc0_production_batch_final``.
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


def _set_pbr(material_name: str, rgba: tuple[float, float, float, float], roughness: float) -> None:
    mat = bpy.data.materials.get(material_name)
    if mat is None or not mat.use_nodes:
        raise RuntimeError(f"missing expected material: {material_name}")
    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        raise RuntimeError(f"missing Principled BSDF: {material_name}")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness


def _scale_existing_meshes(prefixes: tuple[str, ...], factor: Vector) -> int:
    """Enlarge existing local mesh volumes without creating triangles."""
    changed = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not any(obj.name.startswith(prefix) for prefix in prefixes):
            continue
        obj.scale = Vector((obj.scale.x * factor.x, obj.scale.y * factor.y, obj.scale.z * factor.z))
        changed += 1
    bpy.context.view_layer.update()
    return changed


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

    # The first correction is already ~25.8k triangles against a 26k budget.
    # Make every existing pom-pom physically fuller instead of adding more
    # heads.  Petals overlap more, closing the visual gaps while preserving the
    # flower centres and overall true-scale placement.
    flower_count = _scale_existing_meshes(
        (
            "BS_Marigold_",
            "BS_LowerMarigold_",
            "BS_FinalFillMarigold_",
            "BS_FinalCollarMarigold_",
        ),
        Vector((1.24, 1.24, 1.16)),
    )

    # Broaden the foliage that already exists around the long stems.  This is
    # a zero-triangle way to break up the straight-stem lattice seen in the QA
    # front view.  Keep Z growth modest so leaves read wide rather than bulky.
    leaf_count = _scale_existing_meshes(
        (
            "BS_MehndiLeaf",
            "BS_LowerLeaf",
            "BS_FinalFillLeaf",
        ),
        Vector((1.22, 1.22, 1.08)),
    )

    if flower_count == 0 or leaf_count == 0:
        raise RuntimeError(
            f"expected existing marigold geometry was not found: flowers={flower_count}, leaves={leaf_count}"
        )

    # Stronger non-emissive colours survive AgX/studio exposure and make the
    # three warm flower tones clearly different on mobile.  Stems and leaves
    # are intentionally deep green so they recede behind the blooms instead of
    # reading as a pale mint cage.
    _set_pbr("BS_MarigoldOrange", (0.92, 0.012, 0.001, 1.0), 0.56)
    _set_pbr("BS_MarigoldSaffron", (1.00, 0.095, 0.002, 1.0), 0.56)
    _set_pbr("BS_MarigoldYellow", (1.00, 0.40, 0.004, 1.0), 0.58)
    _set_pbr("BS_MehndiStem", (0.006, 0.040, 0.002, 1.0), 0.78)
    _set_pbr("BS_MehndiLeaf", (0.010, 0.085, 0.004, 1.0), 0.75)


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
