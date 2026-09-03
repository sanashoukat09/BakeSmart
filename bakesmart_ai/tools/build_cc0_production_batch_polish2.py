"""Second visual-polish pass for the Batch-1 marigold candidate.

This module deliberately builds on the already validated final Batch-1 builder.
It leaves the approved low floral and corrected mirror implementations exactly
as supplied by ``build_cc0_production_batch_final`` and only adds camouflage,
colour separation and crown density to the marigold floor cluster.
"""
from __future__ import annotations

import math
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


def polished_marigold(row: dict[str, str]) -> None:
    _previous_marigold(row)

    orange = bpy.data.materials.get("BS_MarigoldOrange")
    saffron = bpy.data.materials.get("BS_MarigoldSaffron")
    yellow = bpy.data.materials.get("BS_MarigoldYellow")
    stem = bpy.data.materials.get("BS_MehndiStem")
    leaf = bpy.data.materials.get("BS_MehndiLeaf")
    if not all((orange, saffron, yellow, stem, leaf)):
        raise RuntimeError("second-pass Mehndi materials were not created")

    # Fill the visibly empty middle and upper crown with compact flower heads.
    # These are intentionally clustered around the existing branch structure,
    # not stretched to fill the room. Short local connectors keep the geometry
    # believable while preventing another forest of long straight stems.
    flower_index = 0
    fill_rings = (
        (0.205, 14, 0.565, 0.038),
        (0.155, 12, 0.675, 0.037),
        (0.105, 9, 0.785, 0.036),
    )
    for ring_index, (radius, count, z_base, flower_radius) in enumerate(fill_rings):
        for index in range(count):
            angle = 2 * math.pi * index / count + ring_index * 0.31
            radial = radius * (0.94 + 0.06 * math.sin(index * 1.73 + ring_index))
            x = math.cos(angle) * radial
            y = math.sin(angle) * radial
            z = z_base + 0.020 * math.sin(index * 1.41 + ring_index * 0.7)

            connector_start = (x * 0.72, y * 0.72, z - 0.075)
            base.cylinder_between(
                f"BS_Polish2Stem_{flower_index:02d}",
                connector_start,
                (x, y, z),
                0.0025,
                stem,
                7,
            )
            final.compact_marigold(
                f"BS_Polish2Marigold_{flower_index:02d}",
                (x, y, z),
                orange if (flower_index + ring_index) % 3 else yellow,
                saffron,
                flower_radius,
            )
            # Two overlapping leaves per local connector visually break up the
            # remaining linear stem pattern from front and oblique views.
            midpoint = Vector(connector_start).lerp(Vector((x, y, z)), 0.44)
            base.add_leaf(
                f"BS_Polish2LeafA_{flower_index:02d}",
                midpoint + Vector((0.0, 0.0, -0.005)),
                angle + 0.58,
                leaf,
                0.055,
                0.020,
            )
            base.add_leaf(
                f"BS_Polish2LeafB_{flower_index:02d}",
                midpoint + Vector((0.0, 0.0, 0.012)),
                angle - 0.66,
                leaf,
                0.050,
                0.018,
            )
            flower_index += 1

    # Add a dense foliage collar through the middle of the arrangement. It
    # masks the original straight-stem lattice without increasing footprint.
    for ring_index, (radius, z_base, count) in enumerate(
        ((0.170, 0.505, 20), (0.135, 0.610, 18), (0.095, 0.710, 14))
    ):
        for index in range(count):
            angle = 2 * math.pi * index / count + ring_index * 0.23
            radial = radius * (0.92 + 0.08 * math.sin(index * 1.6))
            location = (
                math.cos(angle) * radial,
                math.sin(angle) * radial,
                z_base + 0.018 * math.sin(index * 1.25 + ring_index),
            )
            base.add_leaf(
                f"BS_Polish2CollarLeaf_{ring_index:02d}_{index:02d}",
                location,
                angle + (0.62 if index % 2 else -0.52),
                leaf,
                0.060 if ring_index == 0 else 0.052,
                0.021 if ring_index == 0 else 0.018,
            )

    # The first correction proved the material assignments work, but AgX/high
    # studio exposure made the hues read peach/cream. Push chroma separation
    # harder while keeping physically ordinary, non-emissive PBR materials.
    _set_pbr("BS_MarigoldOrange", (0.95, 0.018, 0.001, 1.0), 0.56)
    _set_pbr("BS_MarigoldSaffron", (1.00, 0.105, 0.002, 1.0), 0.56)
    _set_pbr("BS_MarigoldYellow", (1.00, 0.43, 0.006, 1.0), 0.58)
    _set_pbr("BS_MehndiStem", (0.008, 0.055, 0.003, 1.0), 0.76)
    _set_pbr("BS_MehndiLeaf", (0.014, 0.115, 0.006, 1.0), 0.73)


base.build_marigold = polished_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
