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


def compact_marigold(name, center, orange, saffron, radius=0.031):
    """Create a visually dense marigold head using mobile-friendly topology."""
    c = Vector(center)
    base.ico(name + "_Core", c, (radius * 0.58, radius * 0.58, radius * 0.52), saffron)
    for ring_index, (count, ring_radius, scale_factor) in enumerate(
        ((5, radius * 0.34, 0.48), (7, radius * 0.62, 0.52))
    ):
        for index in range(count):
            angle = 2 * math.pi * index / count + ring_index * 0.19
            z = 0.0035 * math.sin(index * 1.7 + ring_index)
            location = c + Vector(
                (math.cos(angle) * ring_radius, math.sin(angle) * ring_radius, z)
            )
            petal = base.ico(
                f"{name}_R{ring_index}_{index:02d}",
                location,
                (radius * scale_factor, radius * scale_factor * 0.88, radius * 0.36),
                orange if (index + ring_index) % 2 else saffron,
            )
            petal.rotation_euler[2] = angle


def transform_authored(prefixes, sx=1.0, sy=1.0, sz=1.0, pivot_z=0.0):
    """Apply one world-space transform to authored meshes while preserving joins."""
    scale = Matrix.Diagonal((sx, sy, sz, 1.0))
    transform = (
        Matrix.Translation((0.0, 0.0, pivot_z))
        @ scale
        @ Matrix.Translation((0.0, 0.0, -pivot_z))
    )
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

    # Pull the authored bouquet inward and slightly downward as one world-space
    # composition. This keeps stems attached to heads/leaves but removes the
    # evenly-spread "spokes" seen in the prior QA render.
    transform_authored(("BS_",), sx=0.84, sy=0.84, sz=0.90, pivot_z=0.155)

    # Stronger wedding palette survives neutral/AgX lighting better than the
    # earlier near-white materials while remaining blush/cream rather than neon.
    set_base_color("BS_BlushRose", (0.62, 0.16, 0.19, 1.0))
    set_base_color("BS_PaleBlush", (0.86, 0.48, 0.50, 1.0))
    set_base_color("BS_Ivory", (0.91, 0.76, 0.58, 1.0))
    set_base_color("BS_StemGreen", (0.045, 0.13, 0.035, 1.0))
    set_base_color("BS_LeafGreen", (0.075, 0.22, 0.055, 1.0))


def final_marigold(row):
    _original_marigold(row)

    orange = bpy.data.materials.get("BS_MarigoldOrange")
    saffron = bpy.data.materials.get("BS_MarigoldSaffron")
    yellow = bpy.data.materials.get("BS_MarigoldYellow")
    stem = bpy.data.materials.get("BS_MehndiStem")
    if not all((orange, saffron, yellow, stem)):
        raise RuntimeError("final Mehndi materials were not created")

    # Fill the visual hole between the vessel lip and tall upper tiers with two
    # overlapping rings. These are intentionally short, dense stems so the asset
    # reads as event marigold décor rather than a collection of isolated sticks.
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
                0.032,
            )
            extra_index += 1

    # Tighten the overall floral cone a little while leaving the brass vessel at
    # its verified size. This increases overlap and keeps the true placement
    # envelope conservative.
    transform_authored(("BS_Mehndi", "BS_Marigold", "BS_Lower", "BS_FinalFill"), sx=0.90, sy=0.90, sz=1.0, pivot_z=0.34)

    set_base_color("BS_MarigoldOrange", (0.78, 0.055, 0.006, 1.0))
    set_base_color("BS_MarigoldSaffron", (0.96, 0.24, 0.008, 1.0))
    set_base_color("BS_MarigoldYellow", (0.96, 0.52, 0.015, 1.0))
    set_base_color("BS_MehndiStem", (0.035, 0.105, 0.022, 1.0))
    set_base_color("BS_MehndiLeaf", (0.055, 0.18, 0.035, 1.0))


base.add_marigold = compact_marigold
base.build_low_floral = final_low_floral
base.build_marigold = final_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
