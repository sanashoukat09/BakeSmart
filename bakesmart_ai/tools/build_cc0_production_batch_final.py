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


def set_pbr(material_name, rgba, metallic=None, roughness=None):
    """Set explicit mobile-safe Principled values on an existing material."""
    mat = bpy.data.materials.get(material_name)
    if mat is None or not mat.use_nodes:
        return
    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return
    bsdf.inputs["Base Color"].default_value = rgba
    if metallic is not None:
        bsdf.inputs["Metallic"].default_value = metallic
    if roughness is not None:
        bsdf.inputs["Roughness"].default_value = roughness


def force_material_on_prefix(prefixes, mat):
    """Replace imported source materials when their PBR response is unreliable."""
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not any(obj.name.startswith(prefix) for prefix in prefixes):
            continue
        if len(obj.data.materials) == 0:
            obj.data.materials.append(mat)
        else:
            for index in range(len(obj.data.materials)):
                obj.data.materials[index] = mat


def add_arch_panel(name, width, bottom_z, spring_z, depth, y_center, mat):
    """Create a thin arched mirror inset that remains light without an HDR environment."""
    half = width * 0.5
    profile = [(-half, bottom_z), (half, bottom_z), (half, spring_z)]
    for index in range(1, 9):
        angle = math.pi * index / 8
        profile.append((math.cos(angle) * half, spring_z + math.sin(angle) * half))

    front_y = y_center - depth * 0.5
    back_y = y_center + depth * 0.5
    vertices = [(x, front_y, z) for x, z in profile] + [(x, back_y, z) for x, z in profile]
    count = len(profile)
    faces = [tuple(range(count)), tuple(reversed(range(count, count * 2)))]
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((index, nxt, count + nxt, count + index))

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


_original_low_floral = base.build_low_floral
_original_marigold = base.build_marigold
_original_mirror = base.build_mirror


def final_low_floral(row):
    _original_low_floral(row)
    # Keep the already-approved low-floral composition unchanged.
    transform_authored(("BS_",), sx=1.18, sy=1.18, sz=0.88, pivot_z=0.155)
    set_pbr("BS_BlushRose", (0.42, 0.055, 0.075, 1.0))
    set_pbr("BS_PaleBlush", (0.70, 0.22, 0.25, 1.0))
    set_pbr("BS_Ivory", (0.74, 0.50, 0.30, 1.0))
    set_pbr("BS_StemGreen", (0.025, 0.075, 0.018, 1.0))
    set_pbr("BS_LeafGreen", (0.035, 0.13, 0.025, 1.0))


def final_marigold(row):
    _original_marigold(row)
    orange = bpy.data.materials.get("BS_MarigoldOrange")
    saffron = bpy.data.materials.get("BS_MarigoldSaffron")
    yellow = bpy.data.materials.get("BS_MarigoldYellow")
    stem = bpy.data.materials.get("BS_MehndiStem")
    leaf = bpy.data.materials.get("BS_MehndiLeaf")
    if not all((orange, saffron, yellow, stem, leaf)):
        raise RuntimeError("final Mehndi materials were not created")

    # Make the real CC0 pot robust in glTF/mobile lighting instead of depending
    # on a dark imported material or missing environment reflections.
    brass = base.material(
        "BS_BrassPot",
        (0.82, 0.48, 0.12, 1.0),
        metallic=0.82,
        roughness=0.30,
    )
    force_material_on_prefix(("CC0_Brass",), brass)

    extra_index = 0
    # Wider outer and middle rings fill the 70 cm installation envelope and
    # produce a fuller crown instead of a narrow central spray.
    for ring_radius, count, z_base in ((0.265, 12, 0.50), (0.195, 10, 0.62)):
        for index in range(count):
            angle = 2 * math.pi * index / count + (0.16 if count == 10 else 0.0)
            radial_jitter = ring_radius * (0.96 + 0.04 * math.sin(index * 1.7))
            x = math.cos(angle) * radial_jitter
            y = math.sin(angle) * radial_jitter
            z = z_base + 0.022 * math.sin(index * 1.6 + count * 0.1)
            base.cylinder_between(
                f"BS_FinalFillStem_{extra_index:02d}",
                (x * 0.34, y * 0.34, 0.355),
                (x, y, z),
                0.0030,
                stem,
                7,
            )
            compact_marigold(
                f"BS_FinalFillMarigold_{extra_index:02d}",
                (x, y, z),
                orange if extra_index % 3 else yellow,
                saffron,
                0.034 if count == 12 else 0.033,
            )
            # Add broad foliage near the upper stem so long straight stems do
            # not dominate the silhouette.
            midpoint = Vector((x * 0.34, y * 0.34, 0.355)).lerp(Vector((x, y, z)), 0.58)
            base.add_leaf(
                f"BS_FinalFillLeaf_{extra_index:02d}",
                midpoint,
                angle + (0.55 if index % 2 else -0.48),
                leaf,
                0.048,
                0.016,
            )
            extra_index += 1

    # A low collar of flower heads hides the exposed stem bundle at the pot rim.
    for index in range(10):
        angle = 2 * math.pi * index / 10 + 0.12
        radius = 0.178 + 0.012 * math.sin(index * 1.4)
        center = (
            math.cos(angle) * radius,
            math.sin(angle) * radius,
            0.425 + 0.015 * math.sin(index * 1.9),
        )
        compact_marigold(
            f"BS_FinalCollarMarigold_{index:02d}",
            center,
            yellow if index % 3 == 0 else orange,
            saffron,
            0.031,
        )

    # The outer centers land near 31 cm after this scale, while flower volume
    # fills the 70 cm envelope without oversizing the true-scale module.
    transform_authored(
        ("BS_Mehndi", "BS_Marigold", "BS_Lower", "BS_FinalFill", "BS_FinalCollar"),
        sx=1.18,
        sy=1.18,
        sz=1.0,
        pivot_z=0.34,
    )

    # Keep a strong orange / saffron / yellow separation in sRGB mobile viewers.
    set_pbr("BS_MarigoldOrange", (1.00, 0.20, 0.015, 1.0), roughness=0.54)
    set_pbr("BS_MarigoldSaffron", (1.00, 0.48, 0.035, 1.0), roughness=0.55)
    set_pbr("BS_MarigoldYellow", (1.00, 0.78, 0.12, 1.0), roughness=0.57)
    set_pbr("BS_MehndiStem", (0.055, 0.20, 0.028, 1.0), roughness=0.72)
    set_pbr("BS_MehndiLeaf", (0.085, 0.30, 0.045, 1.0), roughness=0.70)


def final_mirror(row):
    _original_mirror(row)

    # Treat the imported ornate geometry as the frame. The original source can
    # contain dark generic materials that render almost black without an HDRI.
    frame_gold = base.material(
        "BS_MirrorFrameGold",
        (0.84, 0.58, 0.18, 1.0),
        metallic=0.74,
        roughness=0.28,
    )
    force_material_on_prefix(("CC0_Mirror",), frame_gold)

    # Add an explicit silver inset over the imported dark mirror face. A light
    # base color is intentional: real-time/mobile previews cannot rely on scene
    # reflections being available, so pure black metallic would read as a void.
    mirror_silver = base.material(
        "BS_MirrorSilver",
        (0.82, 0.88, 0.94, 1.0),
        metallic=0.88,
        roughness=0.16,
    )
    add_arch_panel(
        "BS_MirrorInset",
        width=0.585,
        bottom_z=0.245,
        spring_z=1.125,
        depth=0.004,
        y_center=-0.021,
        mat=mirror_silver,
    )

    # Rebalance supports and lettering for small-screen contrast.
    set_pbr("BS_Stand", (0.80, 0.53, 0.15, 1.0), metallic=0.70, roughness=0.30)
    set_pbr("BS_WelcomeLettering", (1.00, 0.72, 0.16, 1.0), metallic=0.18, roughness=0.30)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith("BS_WelcomeText"):
            obj.location.y = -0.030
        elif obj.name.startswith("BS_SubtitleText"):
            obj.location.y = -0.030
            obj.scale *= 1.06
    bpy.context.view_layer.update()


base.add_rose = compact_rose
base.add_marigold = compact_marigold
base.build_low_floral = final_low_floral
base.build_marigold = final_marigold
base.build_mirror = final_mirror


if __name__ == "__main__":
    raise SystemExit(base.main())
