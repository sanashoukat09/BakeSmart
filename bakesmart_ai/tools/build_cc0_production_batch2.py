"""Build Batch 2 review-only event assets from CC0 references.

Run with Blender. Geometry is authored deterministically and uses no AI service.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_cc0_production_batch as base


ROOT = Path(__file__).resolve().parents[1]
base.PLAN = ROOT / "data/production_assets_v1/production_batch2_plan.csv"
base.REPORT = ROOT / "data/production_assets_v1/production_candidate_build_report.json"


def emissive(name: str, color: tuple[float, float, float, float], strength: float = 3.0):
    mat = base.material(name, color, roughness=0.30)
    bsdf = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    emission = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    if emission is not None:
        emission.default_value = color
    emission_strength = bsdf.inputs.get("Emission Strength")
    if emission_strength is not None:
        emission_strength.default_value = strength
    return mat


def tube_arc(name: str, radius: float, center_z: float, mat, segments: int = 24, depth_y: float = 0.0, tube_radius: float = 0.015):
    points = []
    for index in range(segments + 1):
        angle = math.pi * index / segments
        points.append((math.cos(angle) * radius, depth_y, center_z + math.sin(angle) * radius))
    for index, (start, end) in enumerate(zip(points, points[1:])):
        base.cylinder_between(f"{name}_{index:02d}", start, end, tube_radius, mat, 10)


def build_round_arch(_row):
    metal = base.material("BS_WarmGoldMetal", (0.82, 0.52, 0.15, 1), metallic=0.82, roughness=0.20)
    fabric_a = base.material("BS_IvoryFabricLight", (0.96, 0.88, 0.77, 1), roughness=0.88)
    for x in (-0.985, 0.985):
        base.cylinder_between("BS_ArchPost", (x, 0, 0.04), (x, 0, 1.215), 0.018, metal, 10)
    tube_arc("BS_ArchTop", 0.982, 1.20, metal, tube_radius=0.018)
    base.cube("BS_FootL", (0.30, 0.55, 0.04), (-0.85, 0, 0.02), metal)
    base.cube("BS_FootR", (0.30, 0.55, 0.04), (0.85, 0, 0.02), metal)
    # One continuous, lightly rippled mesh reads as cloth instead of separate boards.
    columns, rows = 28, 20
    vertices = []
    for row in range(rows + 1):
        v = row / rows
        z = 0.10 + 1.78 * v
        for column in range(columns + 1):
            u = column / columns
            x = -0.72 + 1.44 * u
            fold = 0.045 * math.sin(u * math.tau * 5.0) * (0.72 + 0.28 * math.sin(v * math.pi))
            billow = 0.018 * math.sin(v * math.pi * 2.0 + u * 3.0)
            vertices.append((x, -0.04 + fold + billow, z + 0.018 * math.sin(u * math.pi)))
    faces = []
    stride = columns + 1
    for row in range(rows):
        for column in range(columns):
            a = row * stride + column
            faces.append((a, a + 1, a + stride + 1, a + stride))
    mesh = bpy.data.meshes.new("BS_ContinuousDrapeMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    drape = bpy.data.objects.new("BS_ContinuousDrape", mesh)
    bpy.context.collection.objects.link(drape)
    drape.data.materials.append(fabric_a)
    for polygon in drape.data.polygons:
        polygon.use_smooth = True
    solidify = drape.modifiers.new("BS_ClothThickness", "SOLIDIFY")
    solidify.thickness = 0.006
    bpy.context.view_layer.objects.active = drape
    bpy.ops.object.modifier_apply(modifier=solidify.name)
    # Small top loops visibly attach the removable drape to the metal arch.
    for x in (-0.62, -0.31, 0.0, 0.31, 0.62):
        bpy.ops.mesh.primitive_torus_add(major_segments=12, minor_segments=6, major_radius=0.025, minor_radius=0.006, location=(x, -0.025, 1.89), rotation=(math.pi / 2, 0, 0))
        bpy.context.object.name = "BS_DrapeAttachment"
        bpy.context.object.data.materials.append(fabric_a)


def balloon(name, position, scale, mat):
    obj = base.ico(name, position, scale, mat, subdivisions=3)
    obj.rotation_euler[2] = 0.25 * math.sin(position[0] * 11 + position[2] * 7)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def build_balloon_garland(_row):
    wall = base.material("BS_PhotoWall", (0.86, 0.69, 0.74, 1), roughness=0.70)
    frame = base.material("BS_WhiteFrame", (0.88, 0.88, 0.84, 1), metallic=0.15, roughness=0.43)
    palette = [
        base.material("BS_BalloonBlush", (0.89, 0.43, 0.51, 1), roughness=0.28),
        base.material("BS_BalloonPeach", (0.96, 0.61, 0.39, 1), roughness=0.27),
        base.material("BS_BalloonCream", (0.96, 0.86, 0.69, 1), roughness=0.32),
    ]
    # Extruded arched silhouette gives the photo wall an intentional event-panel finish.
    outline = [(-0.78, 0.10), (0.78, 0.10), (0.78, 1.16)]
    outline.extend((0.78 * math.cos(angle), 1.16 + 0.78 * math.sin(angle)) for angle in [math.pi * i / 16 for i in range(1, 17)])
    depth = 0.05
    vertices = [(x + 0.12, -depth, z) for x, z in outline] + [(x + 0.12, depth, z) for x, z in outline]
    count = len(outline)
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    faces.extend((i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count))
    mesh = bpy.data.meshes.new("BS_ArchedPhotoWallMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    panel = bpy.data.objects.new("BS_ArchedPhotoWall", mesh)
    bpy.context.collection.objects.link(panel)
    panel.data.materials.append(wall)
    bevel = panel.modifiers.new("BS_SoftPanelEdges", "BEVEL")
    bevel.width = 0.025
    bevel.segments = 3
    bpy.context.view_layer.objects.active = panel
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    base.cube("BS_WallFoot", (1.78, 0.55, 0.05), (0.12, 0, 0.025), frame)
    positions = []
    for i in range(23):
        t = i / 22
        positions.append((-0.91 + 0.07 * math.sin(i * 1.8), -0.08 + 0.06 * (i % 3), 0.13 + 1.78 * t))
    for i in range(27):
        t = i / 26
        positions.append((-0.90 + 1.85 * t, -0.07 + 0.055 * (i % 3), 1.89 + 0.08 * math.sin(t * math.pi)))
    # A second, offset layer makes the garland full and organic rather than a bead string.
    for i in range(24):
        if i < 11:
            t = i / 10
            positions.append((-0.76 + 0.08 * math.sin(i), 0.08, 0.36 + 1.38 * t))
        else:
            t = (i - 11) / 12
            positions.append((-0.68 + 1.42 * t, 0.08, 1.73 + 0.07 * math.sin(t * math.pi)))
    for i, pos in enumerate(positions):
        radius = 0.080 + 0.018 * ((i * 7) % 4)
        balloon(f"BS_Balloon_{i:02d}", pos, (radius, radius * 0.92, radius * (1.02 + 0.10 * (i % 2))), palette[i % 3])


def flower(name, position, outer, inner, core, radius=0.13):
    """Build a front-facing, overlapping rosette rather than a bead cluster."""
    center = Vector(position)
    for layer, petal_count in ((0, 10), (1, 7)):
        reach = radius * (0.40 if layer == 0 else 0.22)
        petal_size = radius * (0.39 if layer == 0 else 0.31)
        for i in range(petal_count):
            angle = math.tau * (i + layer * 0.5) / petal_count
            p = center + Vector((math.cos(angle) * reach, -0.010 * layer, math.sin(angle) * reach))
            obj = base.ico(
                f"{name}_Petal_{layer}_{i}",
                p,
                (petal_size, radius * 0.12, petal_size * 0.92),
                outer if layer == 0 else inner,
                subdivisions=2,
            )
            obj.name = f"{name}_Petal_{layer}_{i}"
            obj.rotation_euler[1] = angle
    base.ico(name + "_Core", center + Vector((0, -0.022, 0)), (radius * 0.24, radius * 0.10, radius * 0.24), core, subdivisions=2)


def build_floral_arch(_row):
    stem = base.material("BS_FloralArchStem", (0.16, 0.34, 0.12, 1), roughness=0.72)
    leaf = base.material("BS_FloralArchLeaf", (0.28, 0.48, 0.20, 1), roughness=0.68)
    blush = base.material("BS_FloralBlush", (0.92, 0.54, 0.60, 1), roughness=0.58)
    rose = base.material("BS_FloralRose", (0.76, 0.30, 0.42, 1), roughness=0.60)
    ivory = base.material("BS_FloralIvory", (0.96, 0.88, 0.72, 1), roughness=0.61)
    peach = base.material("BS_FloralPeach", (0.95, 0.68, 0.55, 1), roughness=0.60)
    core = base.material("BS_FloralCore", (0.73, 0.48, 0.12, 1), roughness=0.52)
    for x in (-1.345, 1.345):
        base.cylinder_between("BS_FloralPost", (x, 0, 0.04), (x, 0, 1.10), 0.015, stem, 8)
    tube_arc("BS_FloralArch", 1.345, 1.10, stem, segments=28)
    base.cube("BS_FloralFootL", (0.30, 0.90, 0.04), (-1.25, 0, 0.02), stem)
    base.cube("BS_FloralFootR", (0.30, 0.90, 0.04), (1.25, 0, 0.02), stem)
    points = []
    for i in range(11):
        z = 0.13 + i * 0.095
        points.extend(((-1.31 + 0.045 * math.sin(i), 0.02 * (i % 3), z), (1.31 + 0.045 * math.cos(i), -0.02 * (i % 3), z)))
    for i in range(21):
        angle = math.pi * i / 20
        radius = 1.30 + 0.035 * math.sin(i * 1.7)
        points.append((math.cos(angle) * radius, 0.025 * ((i % 3) - 1), 1.10 + math.sin(angle) * radius))
    palette = [(blush, rose), (ivory, peach), (peach, blush), (rose, blush), (ivory, blush)]
    for i, point in enumerate(points):
        radius = 0.105 + 0.014 * ((i * 5) % 4)
        outer, inner = palette[(i * 3) % len(palette)]
        flower(f"BS_ArchRose_{i:02d}", point, outer, inner, core, radius)
        for side in (-1, 1):
            leaf_position = (point[0] + side * radius * 0.62, point[1] + 0.035, point[2] - radius * 0.42)
            leaf_obj = base.ico(f"BS_ArchLeaf_{i:02d}_{side}", leaf_position, (radius * 0.58, 0.022, radius * 0.23), leaf, subdivisions=2)
            leaf_obj.rotation_euler[1] = side * (0.42 + 0.12 * math.sin(i))


def build_fairy_light_curtain(_row):
    wire = base.material("BS_LightWire", (0.48, 0.38, 0.22, 1), metallic=0.24, roughness=0.62)
    support = base.material("BS_CurtainSupport", (0.62, 0.44, 0.18, 1), metallic=0.58, roughness=0.30)
    glow = emissive("BS_WarmLED", (1.0, 0.68, 0.22, 1), 9.0)
    base.cube("BS_CurtainTop", (3.00, 0.035, 0.028), (0, 0, 2.486), support)
    for col in range(24):
        x = -1.48 + col * (2.96 / 23)
        base.cylinder_between(f"BS_Drop_{col:02d}", (x, 0, 0.02), (x, 0, 2.46), 0.0016, wire, 6)
        for row in range(14):
            z = 0.075 + row * 0.18 + 0.025 * math.sin(col * 1.7 + row)
            base.ico(f"BS_LED_{col:02d}_{row:02d}", (x, -0.033 if (col + row) % 2 else 0.033, z), (0.013, 0.013, 0.018), glow)


def build_uplight_set(_row):
    body = base.material("BS_UplightBody", (0.13, 0.15, 0.18, 1), metallic=0.70, roughness=0.25)
    trim = base.material("BS_UplightTrim", (0.38, 0.42, 0.46, 1), metallic=0.82, roughness=0.20)
    glow = emissive("BS_UplightGlow", (0.32, 0.62, 1.0, 1), 10.0)
    beam = emissive("BS_UplightBeam", (0.18, 0.42, 1.0, 0.22), 2.0)
    base.cube("BS_UplightBase", (0.20, 0.20, 0.045), (0, 0, 0.0225), body)
    for x in (-0.087, 0.087):
        base.cube("BS_UplightBracket", (0.018, 0.11, 0.13), (x, 0, 0.105), trim)
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.078, depth=0.145, location=(0, 0, 0.15), rotation=(math.radians(18), 0, 0))
    fixture = bpy.context.object
    fixture.name = "BS_UplightFixture"
    fixture.data.materials.append(body)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.067, depth=0.014, location=(0, -0.023, 0.218), rotation=(math.radians(18), 0, 0))
    lens = bpy.context.object
    lens.name = "BS_UplightLens"
    lens.data.materials.append(glow)
    for angle in range(0, 360, 45):
        a = math.radians(angle)
        base.ico("BS_LensLED", (math.cos(a) * 0.038, -0.031, 0.218 + math.sin(a) * 0.038), (0.010, 0.006, 0.010), glow)
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.060, radius2=0.015, depth=0.11, location=(0, -0.04, 0.205), rotation=(math.radians(18), 0, 0))
    bpy.context.object.name = "BS_VisibleLightBeam"
    bpy.context.object.data.materials.append(beam)


def build_led_candles(_row):
    wax = base.material("BS_LEDWax", (0.97, 0.84, 0.62, 1), roughness=0.70)
    rim = base.material("BS_MeltedWax", (1.0, 0.91, 0.72, 1), roughness=0.62)
    wick = base.material("BS_LEDWireWick", (0.18, 0.10, 0.05, 1), roughness=0.80)
    glow = emissive("BS_LEDFlame", (1.0, 0.50, 0.10, 1), 9.0)
    specs = [(-0.017, 0.006, 0.024, 0.142), (0.017, 0.016, 0.020, 0.112), (0.020, -0.018, 0.018, 0.082), (-0.024, -0.021, 0.017, 0.094), (0.002, -0.006, 0.015, 0.065)]
    for i, (x, y, radius, height) in enumerate(specs):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=height, location=(x, y, height / 2))
        candle = bpy.context.object
        candle.name = f"BS_LEDCandle_{i:02d}"
        candle.data.materials.append(wax)
        bevel = candle.modifiers.new("BS_WaxEdge", "BEVEL")
        bevel.width = 0.003
        bevel.segments = 2
        bpy.context.view_layer.objects.active = candle
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        bpy.ops.mesh.primitive_torus_add(major_segments=20, minor_segments=6, location=(x, y, height), major_radius=radius * 0.70, minor_radius=radius * 0.10)
        bpy.context.object.data.materials.append(rim)
        base.cylinder_between(f"BS_Wick_{i:02d}", (x, y, height), (x, y, height + 0.008), 0.0012, wick, 6)
        flame_z = min(0.174, height + 0.016)
        flame = base.ico(f"BS_LEDFlame_{i:02d}", (x, y, flame_z), (0.007, 0.006, 0.015), glow, subdivisions=2)
        flame.rotation_euler[1] = 0.18 * math.sin(i)


BUILDERS = {
    "round_arch": build_round_arch,
    "balloon_garland": build_balloon_garland,
    "floral_arch": build_floral_arch,
    "fairy_light_curtain": build_fairy_light_curtain,
    "uplight_set": build_uplight_set,
    "led_candles": build_led_candles,
}
MANIFEST_BY_ID = {row["asset_id"]: row for row in base.read_rows(base.MANIFEST)}


def build(row):
    try:
        BUILDERS[row["builder"]](row)
    except KeyError as exc:
        raise RuntimeError(f"unknown Batch 2 builder {row['builder']}") from exc
    manifest = MANIFEST_BY_ID[row["asset_id"]]
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    base.fit_exact(
        meshes,
        float(manifest["width_m"]),
        float(manifest["depth_m"]),
        float(manifest["height_m"]),
        0.0,
    )


if __name__ == "__main__":
    base.build = build
    raise SystemExit(base.main())
