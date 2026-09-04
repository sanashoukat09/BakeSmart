"""Build Batch 2 review-only event assets from CC0 references.

Run with Blender. Geometry is authored deterministically and uses no AI service.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector

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


def tube_arc(name: str, radius: float, center_z: float, mat, segments: int = 24, depth_y: float = 0.0):
    points = []
    for index in range(segments + 1):
        angle = math.pi * index / segments
        points.append((math.cos(angle) * radius, depth_y, center_z + math.sin(angle) * radius))
    for index, (start, end) in enumerate(zip(points, points[1:])):
        base.cylinder_between(f"{name}_{index:02d}", start, end, 0.015, mat, 8)


def build_round_arch(_row):
    metal = base.material("BS_WarmGoldMetal", (0.58, 0.30, 0.08, 1), metallic=0.78, roughness=0.25)
    fabric = base.material("BS_RemovableIvoryFabric", (0.91, 0.80, 0.68, 1), roughness=0.82)
    base.cube("BS_FabricPanel", (1.64, 0.035, 1.76), (0, 0.0, 0.90), fabric)
    for x in (-0.985, 0.985):
        base.cylinder_between("BS_ArchPost", (x, 0, 0.04), (x, 0, 1.215), 0.015, metal, 8)
    tube_arc("BS_ArchTop", 0.985, 1.20, metal)
    base.cube("BS_FootL", (0.30, 0.55, 0.04), (-0.85, 0, 0.02), metal)
    base.cube("BS_FootR", (0.30, 0.55, 0.04), (0.85, 0, 0.02), metal)


def balloon(name, position, scale, mat):
    obj = base.ico(name, position, scale, mat, subdivisions=2)
    obj.rotation_euler[2] = 0.25 * math.sin(position[0] * 11 + position[2] * 7)
    return obj


def build_balloon_garland(_row):
    wall = base.material("BS_PhotoWall", (0.86, 0.69, 0.74, 1), roughness=0.70)
    frame = base.material("BS_WhiteFrame", (0.88, 0.88, 0.84, 1), metallic=0.15, roughness=0.43)
    palette = [
        base.material("BS_BalloonBlush", (0.89, 0.43, 0.51, 1), roughness=0.28),
        base.material("BS_BalloonPeach", (0.96, 0.61, 0.39, 1), roughness=0.27),
        base.material("BS_BalloonCream", (0.96, 0.86, 0.69, 1), roughness=0.32),
    ]
    base.cube("BS_PhotoWall", (1.68, 0.10, 1.94), (0.12, 0, 1.07), wall)
    base.cube("BS_WallFoot", (1.78, 0.55, 0.05), (0.12, 0, 0.025), frame)
    positions = []
    for i in range(15):
        t = i / 14
        positions.append((-0.92 + 0.10 * math.sin(i), -0.02, 0.18 + 1.70 * t))
    for i in range(13):
        angle = math.pi * i / 24
        positions.append((-0.82 + 1.75 * math.sin(angle), -0.02, 1.82 + 0.09 * math.sin(angle)))
    for i, pos in enumerate(positions):
        radius = 0.095 + 0.015 * ((i * 7) % 4)
        balloon(f"BS_Balloon_{i:02d}", pos, (radius, radius * 0.86, radius * 1.12), palette[i % 3])


def flower(name, position, petal, core, radius=0.055):
    base.ico(name + "_Core", position, (radius * 0.35,) * 3, core)
    center = Vector(position)
    for i in range(6):
        angle = math.tau * i / 6
        p = center + Vector((math.cos(angle) * radius * 0.55, 0, math.sin(angle) * radius * 0.55))
        obj = base.ico(f"{name}_Petal_{i}", p, (radius * 0.55, radius * 0.24, radius * 0.32), petal)
        obj.rotation_euler[1] = angle


def build_floral_arch(_row):
    stem = base.material("BS_FloralArchStem", (0.16, 0.34, 0.12, 1), roughness=0.72)
    leaf = base.material("BS_FloralArchLeaf", (0.28, 0.48, 0.20, 1), roughness=0.68)
    blush = base.material("BS_FloralBlush", (0.92, 0.54, 0.60, 1), roughness=0.58)
    ivory = base.material("BS_FloralIvory", (0.96, 0.88, 0.72, 1), roughness=0.61)
    core = base.material("BS_FloralCore", (0.73, 0.48, 0.12, 1), roughness=0.52)
    for x in (-1.345, 1.345):
        base.cylinder_between("BS_FloralPost", (x, 0, 0.04), (x, 0, 1.10), 0.015, stem, 8)
    tube_arc("BS_FloralArch", 1.345, 1.10, stem, segments=28)
    base.cube("BS_FloralFootL", (0.30, 0.90, 0.04), (-1.25, 0, 0.02), stem)
    base.cube("BS_FloralFootR", (0.30, 0.90, 0.04), (1.25, 0, 0.02), stem)
    points = []
    for i in range(17):
        points.append((-1.34, -0.02, 0.15 + i * 0.068))
        points.append((1.34, 0.02, 0.15 + i * 0.068))
    for i in range(29):
        angle = math.pi * i / 28
        points.append((math.cos(angle) * 1.34, 0.02 * math.sin(i), 1.10 + math.sin(angle) * 1.34))
    for i, point in enumerate(points):
        radius = 0.045 if i % 3 else 0.055
        flower(f"BS_ArchFlower_{i:02d}", point, blush if i % 2 else ivory, core, radius)
        if i % 2:
            base.ico(f"BS_ArchLeaf_{i:02d}", (point[0] * 0.98, 0.04, point[2] - 0.035), (0.065, 0.018, 0.025), leaf)


def build_fairy_light_curtain(_row):
    wire = base.material("BS_LightWire", (0.22, 0.17, 0.10, 1), metallic=0.35, roughness=0.55)
    glow = emissive("BS_WarmLED", (1.0, 0.55, 0.16, 1), 5.0)
    base.cube("BS_CurtainTop", (3.00, 0.04, 0.04), (0, 0, 2.48), wire)
    for col in range(16):
        x = -1.48 + col * (2.96 / 15)
        base.cylinder_between(f"BS_Drop_{col:02d}", (x, 0, 0.02), (x, 0, 2.46), 0.0022, wire, 6)
        for row in range(10):
            z = 0.10 + row * 0.255 + 0.035 * math.sin(col * 1.7 + row)
            base.ico(f"BS_LED_{col:02d}_{row:02d}", (x, -0.035 if (col + row) % 2 else 0.035, z), (0.012, 0.012, 0.016), glow)


def build_uplight_set(_row):
    body = base.material("BS_UplightBody", (0.08, 0.09, 0.11, 1), metallic=0.55, roughness=0.32)
    glow = emissive("BS_UplightGlow", (0.35, 0.55, 1.0, 1), 6.0)
    base.cube("BS_UplightBase", (0.20, 0.20, 0.055), (0, 0, 0.0275), body)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.09, depth=0.17, location=(0, 0, 0.14))
    fixture = bpy.context.object
    fixture.name = "BS_UplightFixture"
    fixture.data.materials.append(body)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.072, depth=0.012, location=(0, -0.006, 0.225))
    lens = bpy.context.object
    lens.name = "BS_UplightLens"
    lens.data.materials.append(glow)


def build_led_candles(_row):
    wax = base.material("BS_LEDWax", (0.94, 0.80, 0.57, 1), roughness=0.78)
    glow = emissive("BS_LEDFlame", (1.0, 0.42, 0.08, 1), 4.5)
    specs = [(-0.012, 0.008, 0.028, 0.145), (0.018, 0.018, 0.023, 0.105), (0.014, -0.018, 0.018, 0.078)]
    for i, (x, y, radius, height) in enumerate(specs):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=height, location=(x, y, height / 2))
        candle = bpy.context.object
        candle.name = f"BS_LEDCandle_{i:02d}"
        candle.data.materials.append(wax)
        flame_z = min(0.173, height + 0.015)
        base.ico(f"BS_LEDFlame_{i:02d}", (x, y, flame_z), (0.007, 0.007, 0.014), glow)


BUILDERS = {
    "round_arch": build_round_arch,
    "balloon_garland": build_balloon_garland,
    "floral_arch": build_floral_arch,
    "fairy_light_curtain": build_fairy_light_curtain,
    "uplight_set": build_uplight_set,
    "led_candles": build_led_candles,
}


def build(row):
    try:
        BUILDERS[row["builder"]](row)
    except KeyError as exc:
        raise RuntimeError(f"unknown Batch 2 builder {row['builder']}") from exc


if __name__ == "__main__":
    base.build = build
    raise SystemExit(base.main())
