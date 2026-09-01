"""Final Batch-1 build entrypoint with mobile-budget floral topology.

This wraps the reviewed production builder and applies the final composition
polish used for Batch-1 visual QA. Physical envelopes, provenance and structural
validation remain authoritative.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_cc0_production_batch as base


def compact_rose(name, center, outer, inner, radius=0.027):
    """Build a small cup-shaped rose head instead of a flat radial disc."""
    c = Vector(center)
    base.ico(name + "_Center", c + Vector((0, 0, radius * 0.08)), (radius * 0.46, radius * 0.46, radius * 0.44), inner)
    petals = (
        (0.00, 0.36, 0.12),
        (0.90, 0.37, 0.10),
        (1.80, 0.39, 0.08),
        (2.70, 0.36, 0.11),
        (3.60, 0.40, 0.07),
        (4.50, 0.37, 0.10),
        (5.40, 0.39, 0.08),
        (0.45, 0.62, -0.01),
        (1.75, 0.64, 0.00),
        (3.05, 0.61, -0.02),
        (4.35, 0.65, 0.01),
        (5.65, 0.62, -0.01),
    )
    for index, (angle, ring, z_offset) in enumerate(petals):
        position = c + Vector((math.cos(angle) * radius * ring, math.sin(angle) * radius * ring, radius * z_offset))
        petal = base.ico(
            f"{name}_Petal_{index:02d}",
            position,
            (radius * 0.48, radius * 0.33, radius * 0.30),
            outer if index >= 7 else inner,
        )
        petal.rotation_euler[2] = angle
        petal.rotation_euler[0] = 0.44 if index >= 7 else 0.26
        petal.rotation_euler[1] = 0.16 * math.sin(angle)


def compact_marigold(name, center, orange, saffron, radius=0.031):
    """Build a rounded pom-pom marigold using low-poly florets."""
    c = Vector(center)
    base.ico(name + "_Core", c, (radius * 0.62, radius * 0.62, radius * 0.60), saffron)
    # Ten florets distributed around a shallow sphere give the head volume from
    # front, side and top views without the cost of the earlier flat 2-ring disc.
    points = (
        (0.0, 0.52, 0.18), (0.63, 0.50, 0.12), (1.26, 0.52, -0.02),
        (1.89, 0.49, 0.15), (2.52, 0.53, -0.08), (3.15, 0.50, 0.10),
        (3.78, 0.52, -0.03), (4.41, 0.50, 0.14), (5.04, 0.53, -0.06),
        (5.67, 0.50, 0.11),
    )
    for index, (angle, ring, z_ratio) in enumerate(points):
        location = c + Vector((math.cos(angle) * radius * ring, math.sin(angle) * radius * ring, radius * z_ratio))
        floret = base.ico(
            f"{name}_Floret_{index:02d}",
            location,
            (radius * 0.47, radius * 0.43, radius * 0.44),
            orange if index % 2 else saffron,
        )
        floret.rotation_euler[2] = angle
        floret.rotation_euler[0] = 0.20 * math.sin(angle)


def transform_authored(prefixes, sx=1.0, sy=1.0, sz=1.0, pivot_z=0.0):
    scale = Matrix.Diagonal((sx, sy, sz, 1.0))
    transform = Matrix.Translation((0.0, 0.0, pivot_z)) @ scale @ Matrix.Translation((0.0, 0.0, -pivot_z))
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and any(obj.name.startswith(prefix) for prefix in prefixes):
            obj.matrix_world = transform @ obj.matrix_world
    bpy.context.view_layer.update()


def set_base_color(material_name, rgba):
    mat = bpy.data.materials.get(material_name)
    if mat is None or not mat.use_nodes:
        return
    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = rgba


_original_low_floral = base.build_low_floral
_original_marigold = base.build_marigold


def final_low_floral(row):
    _original_low_floral(row)
    # Fill the advertised 45 cm centerpiece footprint. The previous 0.82
    # horizontal scale produced only 27.3 cm of visible width/depth.
    transform_authored(("BS_",), sx=1.18, sy=1.18, sz=0.88, pivot_z=0.155)
    set_base_color("BS_BlushRose", (0.42, 0.055, 0.075, 1.0))
    set_base_color("BS_PaleBlush", (0.70, 0.22, 0.25, 1.0))
    set_base_color("BS_Ivory", (0.74, 0.50, 0.30, 1.0))
    set_base_color("BS_StemGreen", (0.025, 0.075, 0.018, 1.0))
    set_base_color("BS_LeafGreen", (0.035, 0.13, 0.025, 1.0))


def final_marigold(row):
    _original_marigold(row)
    orange = bpy.data.materials.get("BS_MarigoldOrange")
    saffron = bpy.data.materials.get("BS_MarigoldSaffron")
    yellow = bpy.data.materials.get("BS_MarigoldYellow")
    stem = bpy.data.materials.get("BS_MehndiStem")
    if not all((orange, saffron, yellow, stem)):
        raise RuntimeError("final Mehndi materials were not created")

    extra_index = 0
    for ring_radius, count, z_base in ((0.145, 8, 0.53), (0.105, 7, 0.64)):
        for index in range(count):
            angle = 2 * math.pi * index / count + (0.20 if count == 7 else 0.0)
            x = math.cos(angle) * ring_radius
            y = math.sin(angle) * ring_radius
            z = z_base + 0.018 * math.sin(index * 1.6)
            base.cylinder_between(
                f"BS_FinalFillStem_{extra_index:02d}",
                (x * 0.22, y * 0.22, 0.325),
                (x, y, z),
                0.0032,
                stem,
                7,
            )
            compact_marigold(
                f"BS_FinalFillMarigold_{extra_index:02d}",
                (x, y, z),
                orange if extra_index % 3 else yellow,
                saffron,
                0.033,
            )
            extra_index += 1

    # The installation envelope is 70 cm square; keep the visible floral crown
    # above the 85% true-scale gate instead of leaving a tiny central cluster.
    transform_authored(
        ("BS_Mehndi", "BS_Marigold", "BS_Lower", "BS_FinalFill"),
        sx=1.18,
        sy=1.18,
        sz=1.0,
        pivot_z=0.34,
    )
    set_base_color("BS_MarigoldOrange", (0.42, 0.012, 0.001, 1.0))
    set_base_color("BS_MarigoldSaffron", (0.68, 0.065, 0.002, 1.0))
    set_base_color("BS_MarigoldYellow", (0.72, 0.20, 0.002, 1.0))
    set_base_color("BS_MehndiStem", (0.018, 0.060, 0.010, 1.0))
    set_base_color("BS_MehndiLeaf", (0.025, 0.095, 0.014, 1.0))


base.add_rose = compact_rose
base.add_marigold = compact_marigold
base.build_low_floral = final_low_floral
base.build_marigold = final_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
