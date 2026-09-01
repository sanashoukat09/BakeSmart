"""Build final-review BakeSmart GLBs from vetted CC0 model sources.

Run with Blender. This is deterministic local asset processing, not AI.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/production_assets_v1/production_batch1_plan.csv"
MANIFEST = ROOT / "data/production_assets_v1/asset_manifest.csv"
RAW = ROOT / "assets/third_party_cc0/raw"
WORK = ROOT / "assets/third_party_cc0/working"
REPORT = ROOT / "data/production_assets_v1/production_candidate_build_report.json"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--asset-id", action="append")
    parser.add_argument("--report", type=Path, default=REPORT)
    return parser.parse_args(argv)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def source_file(source_id: str) -> Path:
    source_id = source_id.strip()
    if not source_id:
        raise RuntimeError("source id must not be empty")
    folder = RAW / source_id
    if not folder.is_dir():
        raise RuntimeError(f"missing downloaded source: {folder}")
    archives = sorted(folder.glob("*.zip"))
    search = folder
    if archives:
        search = WORK / source_id
        shutil.rmtree(search, ignore_errors=True)
        search.mkdir(parents=True)
        with zipfile.ZipFile(archives[0]) as archive:
            archive.extractall(search)
    found = sorted(search.rglob("*.glb")) + sorted(search.rglob("*.gltf"))
    if not found:
        raise RuntimeError(f"no glTF/GLB in {folder}")
    return found[0]


def import_source(source_id: str, prefix: str) -> list[bpy.types.Object]:
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(source_file(source_id)))
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    for obj in list(imported):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
            imported.remove(obj)
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"{source_id} has no mesh")
    for index, obj in enumerate(meshes, 1):
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
        obj.name = f"{prefix}_{index:02d}"
    for obj in list(imported):
        if obj.type == "EMPTY" and obj.users_collection:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    return meshes


def mesh_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not points:
        raise RuntimeError("no mesh bounds")
    minimum = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    maximum = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    return minimum, maximum


def move(objects: list[bpy.types.Object], delta: Vector) -> None:
    for obj in objects:
        obj.location += delta


def fit_exact(objects: list[bpy.types.Object], width: float, depth: float, height: float, z: float) -> None:
    minimum, maximum = mesh_bounds(objects)
    center = (minimum + maximum) / 2
    move(objects, Vector((-center.x, -center.y, -minimum.z)))
    minimum, maximum = mesh_bounds(objects)
    dimensions = maximum - minimum
    scale = Vector(
        (
            width / max(dimensions.x, 1e-6),
            depth / max(dimensions.y, 1e-6),
            height / max(dimensions.z, 1e-6),
        )
    )
    for obj in objects:
        obj.location = Vector(
            (obj.location.x * scale.x, obj.location.y * scale.y, obj.location.z * scale.z)
        )
        obj.scale = Vector(
            (obj.scale.x * scale.x, obj.scale.y * scale.y, obj.scale.z * scale.z)
        )
    bpy.context.view_layer.update()
    minimum, maximum = mesh_bounds(objects)
    center = (minimum + maximum) / 2
    move(objects, Vector((-center.x, -center.y, z - minimum.z)))


def material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, roughness: float = 0.45) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def smooth(obj: bpy.types.Object) -> bpy.types.Object:
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def cube(name: str, dimensions: tuple[float, float, float], location: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def ico(name: str, location: tuple[float, float, float] | Vector, scale: tuple[float, float, float], mat: bpy.types.Material, subdivisions: int = 1) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return smooth(obj)


def cylinder_between(name: str, start: tuple[float, float, float], end: tuple[float, float, float], radius: float, mat: bpy.types.Material, vertices: int = 8) -> bpy.types.Object | None:
    point_a = Vector(start)
    point_b = Vector(end)
    delta = point_b - point_a
    length = delta.length
    if length <= 1e-6:
        return None
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=length,
        location=(point_a + point_b) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return smooth(obj)


def add_leaf(name: str, location: tuple[float, float, float] | Vector, angle: float, mat: bpy.types.Material, length: float = 0.035, width: float = 0.013) -> bpy.types.Object:
    leaf = ico(name, location, (length, width, 0.0045), mat)
    leaf.rotation_euler[2] = angle
    leaf.rotation_euler[0] = 0.18
    return leaf


def add_daisy(name: str, center: tuple[float, float, float], petal: bpy.types.Material, core: bpy.types.Material, petal_radius: float = 0.021) -> None:
    c = Vector(center)
    ico(name + "_Core", c, (0.010, 0.010, 0.008), core)
    for index in range(8):
        angle = 2 * math.pi * index / 8
        position = c + Vector((math.cos(angle) * petal_radius * 0.66, math.sin(angle) * petal_radius * 0.66, 0))
        obj = ico(
            f"{name}_Petal_{index:02d}",
            position,
            (petal_radius * 0.58, petal_radius * 0.25, 0.0048),
            petal,
        )
        obj.rotation_euler[2] = angle


def add_rose(name: str, center: tuple[float, float, float], outer: bpy.types.Material, inner: bpy.types.Material, radius: float = 0.027) -> None:
    c = Vector(center)
    ico(name + "_Center", c + Vector((0, 0, 0.003)), (radius * 0.43, radius * 0.43, radius * 0.38), inner)
    for ring_index, (count, ring_radius, scale_factor, z_offset) in enumerate(
        ((7, radius * 0.40, 0.45, 0.002), (10, radius * 0.66, 0.48, -0.001))
    ):
        for index in range(count):
            angle = 2 * math.pi * index / count + ring_index * 0.21
            location = c + Vector((math.cos(angle) * ring_radius, math.sin(angle) * ring_radius, z_offset))
            petal = ico(
                f"{name}_R{ring_index}_{index:02d}",
                location,
                (radius * scale_factor, radius * scale_factor * 0.74, radius * 0.28),
                outer if ring_index else inner,
            )
            petal.rotation_euler[2] = angle
            petal.rotation_euler[0] = 0.22 if ring_index else 0.10


def add_marigold(name: str, center: tuple[float, float, float], orange: bpy.types.Material, saffron: bpy.types.Material, radius: float = 0.031) -> None:
    c = Vector(center)
    ico(name + "_Core", c, (radius * 0.55, radius * 0.55, radius * 0.50), saffron)
    for ring_index, (count, ring_radius, scale_factor) in enumerate(
        ((9, radius * 0.34, 0.42), (12, radius * 0.58, 0.46))
    ):
        for index in range(count):
            angle = 2 * math.pi * index / count + ring_index * 0.13
            location = c + Vector(
                (
                    math.cos(angle) * ring_radius,
                    math.sin(angle) * ring_radius,
                    0.003 * math.sin(index * 1.7),
                )
            )
            ico(
                f"{name}_R{ring_index}_{index:02d}",
                location,
                (radius * scale_factor, radius * scale_factor, radius * 0.34),
                orange if (index + ring_index) % 2 else saffron,
            )


def add_text_mesh(body: str, name: str, location: tuple[float, float, float], mat: bpy.types.Material, target_width: float, size: float) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location, rotation=(math.radians(90), 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.003
    obj.data.bevel_depth = 0.001
    bpy.context.view_layer.update()
    if obj.dimensions.x > 1e-6:
        obj.scale *= target_width / obj.dimensions.x
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    obj.data.materials.append(mat)
    return obj


def build_low_floral(row: dict[str, str]) -> None:
    vase = import_source(row["primary_source_id"], "CC0_Vase")
    fit_exact(vase, 0.155, 0.155, 0.155, 0.0)

    stem_green = material("BS_StemGreen", (0.075, 0.19, 0.07, 1), roughness=0.72)
    leaf_green = material("BS_LeafGreen", (0.12, 0.31, 0.10, 1), roughness=0.70)
    blush = material("BS_BlushRose", (0.80, 0.38, 0.39, 1), roughness=0.54)
    pale_blush = material("BS_PaleBlush", (0.94, 0.70, 0.69, 1), roughness=0.58)
    ivory = material("BS_Ivory", (0.96, 0.90, 0.78, 1), roughness=0.60)
    core = material("BS_FlowerCore", (0.73, 0.44, 0.10, 1), metallic=0.03, roughness=0.48)

    rose_heads = [
        (-0.105, -0.050, 0.235, 0.030), (-0.082, 0.045, 0.252, 0.028),
        (-0.055, -0.090, 0.246, 0.027), (-0.030, 0.010, 0.273, 0.031),
        (0.000, -0.060, 0.264, 0.029), (0.028, 0.040, 0.278, 0.030),
        (0.060, -0.080, 0.249, 0.027), (0.083, 0.025, 0.259, 0.029),
        (0.108, 0.072, 0.235, 0.027), (-0.118, 0.083, 0.226, 0.026),
        (-0.010, 0.112, 0.238, 0.026), (0.105, -0.105, 0.225, 0.026),
        (-0.075, 0.105, 0.236, 0.026), (0.065, 0.105, 0.244, 0.027),
    ]
    for index, (x, y, z, radius) in enumerate(rose_heads):
        base = (x * 0.20, y * 0.20, 0.142)
        cylinder_between(f"BS_RoseStem_{index:02d}", base, (x, y, z), 0.0025, stem_green, 7)
        midpoint = Vector(base).lerp(Vector((x, y, z)), 0.54)
        add_leaf(f"BS_RoseLeafA_{index:02d}", midpoint + Vector((0.006, -0.004, 0.002)), math.atan2(y, x) + 0.55, leaf_green, 0.032, 0.012)
        if index % 2 == 0:
            add_leaf(f"BS_RoseLeafB_{index:02d}", midpoint + Vector((-0.007, 0.005, -0.003)), math.atan2(y, x) - 0.65, leaf_green, 0.028, 0.010)
        add_rose(f"BS_Rose_{index:02d}", (x, y, z), blush if index % 3 else pale_blush, pale_blush if index % 2 else ivory, radius)

    filler_heads = [
        (-0.145, -0.010, 0.220), (-0.130, 0.118, 0.214), (-0.018, -0.145, 0.225),
        (0.135, -0.020, 0.220), (0.145, 0.105, 0.212), (0.005, 0.145, 0.218),
        (-0.142, -0.112, 0.208), (0.132, -0.125, 0.207),
    ]
    for index, end in enumerate(filler_heads):
        base = (end[0] * 0.16, end[1] * 0.16, 0.143)
        cylinder_between(f"BS_FillerStem_{index:02d}", base, end, 0.0021, stem_green, 6)
        midpoint = Vector(base).lerp(Vector(end), 0.58)
        add_leaf(f"BS_FillerLeaf_{index:02d}", midpoint, math.atan2(end[1], end[0]) + 0.7, leaf_green, 0.030, 0.010)
        add_daisy(f"BS_Filler_{index:02d}", end, ivory if index % 2 else pale_blush, core, 0.018)

    for index in range(18):
        angle = 2 * math.pi * index / 18
        radius = 0.082 + 0.018 * math.sin(index * 1.9)
        location = (math.cos(angle) * radius, math.sin(angle) * radius, 0.180 + 0.010 * math.sin(index * 1.4))
        add_leaf(f"BS_CollarLeaf_{index:02d}", location, angle + 0.35, leaf_green, 0.043, 0.016)


def build_marigold(row: dict[str, str]) -> None:
    brass = import_source(row["primary_source_id"], "CC0_Brass")
    fit_exact(brass, 0.34, 0.34, 0.34, 0.0)

    deep_green = material("BS_MehndiStem", (0.065, 0.17, 0.045, 1), roughness=0.74)
    leaf_green = material("BS_MehndiLeaf", (0.11, 0.27, 0.07, 1), roughness=0.72)
    orange = material("BS_MarigoldOrange", (0.96, 0.25, 0.025, 1), roughness=0.56)
    saffron = material("BS_MarigoldSaffron", (1.0, 0.52, 0.035, 1), roughness=0.55)
    yellow = material("BS_MarigoldYellow", (0.98, 0.72, 0.06, 1), roughness=0.58)

    tiers = [
        (0.235, 16, 0.62, 0.030),
        (0.165, 14, 0.76, 0.031),
        (0.092, 10, 0.90, 0.029),
        (0.035, 5, 0.975, 0.028),
    ]
    head_index = 0
    for tier_index, (ring_radius, count, base_z, flower_radius) in enumerate(tiers):
        for index in range(count):
            angle = 2 * math.pi * index / count + tier_index * 0.27
            radial_variation = ring_radius * (0.92 + 0.08 * math.sin(index * 1.7 + tier_index))
            x = math.cos(angle) * radial_variation
            y = math.sin(angle) * radial_variation
            z = base_z + 0.038 * math.sin(index * 1.37 + tier_index * 0.8)
            end = (x, y, z)
            base = (x * 0.20, y * 0.20, 0.305)
            cylinder_between(f"BS_MehndiStem_{head_index:02d}", base, end, 0.0034, deep_green, 7)
            midpoint = Vector(base).lerp(Vector(end), 0.58)
            add_leaf(f"BS_MehndiLeafA_{head_index:02d}", midpoint, angle + 0.55, leaf_green, 0.050 if tier_index < 2 else 0.042, 0.015)
            if index % 2 == 0:
                add_leaf(f"BS_MehndiLeafB_{head_index:02d}", midpoint + Vector((0.0, 0.0, -0.045)), angle - 0.60, leaf_green, 0.042, 0.013)
            add_marigold(f"BS_Marigold_{head_index:02d}", end, orange if head_index % 3 else yellow, saffron, flower_radius)
            head_index += 1

    for index in range(20):
        angle = 2 * math.pi * index / 20
        radius = 0.145 + 0.020 * math.sin(index * 1.3)
        center = (math.cos(angle) * radius, math.sin(angle) * radius, 0.455 + 0.025 * math.sin(index * 1.8))
        if index % 2:
            add_marigold(f"BS_LowerMarigold_{index:02d}", center, orange, saffron, 0.026)
        else:
            add_leaf(f"BS_LowerLeaf_{index:02d}", center, angle + 0.4, leaf_green, 0.056, 0.018)


def tune_mirror_materials(objects: list[bpy.types.Object]) -> None:
    seen: set[bpy.types.Material] = set()
    for obj in objects:
        for mat in obj.data.materials:
            if mat is None or mat in seen or not mat.use_nodes:
                continue
            seen.add(mat)
            bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
            if bsdf is None:
                continue
            name = mat.name.lower()
            if "mirror" in name or "glass" in name:
                bsdf.inputs["Metallic"].default_value = 0.92
                bsdf.inputs["Roughness"].default_value = 0.10
            elif "gold" in name or "metal" in name or "frame" in name:
                bsdf.inputs["Metallic"].default_value = max(float(bsdf.inputs["Metallic"].default_value), 0.72)
                bsdf.inputs["Roughness"].default_value = min(float(bsdf.inputs["Roughness"].default_value), 0.26)


def build_mirror(row: dict[str, str]) -> None:
    mirror = import_source(row["primary_source_id"], "CC0_Mirror")
    fit_exact(mirror, 0.70, 0.035, 1.34, 0.16)
    tune_mirror_materials(mirror)
    stand = material("BS_Stand", (0.68, 0.52, 0.20, 1), metallic=0.72, roughness=0.27)
    lettering = material("BS_WelcomeLettering", (0.91, 0.72, 0.28, 1), metallic=0.48, roughness=0.25)
    cube("BS_FootL", (0.16, 0.05, 0.025), (-0.27, 0, 0.0125), stand)
    cube("BS_FootR", (0.16, 0.05, 0.025), (0.27, 0, 0.0125), stand)
    cube("BS_BracketL", (0.028, 0.04, 0.16), (-0.30, 0, 0.09), stand)
    cube("BS_BracketR", (0.028, 0.04, 0.16), (0.30, 0, 0.09), stand)
    add_text_mesh("Welcome", "BS_WelcomeText", (0, -0.023, 0.99), lettering, 0.36, 0.18)
    add_text_mesh("Celebrate with us", "BS_SubtitleText", (0, -0.023, 0.86), lettering, 0.30, 0.08)


def build(row: dict[str, str]) -> None:
    builder = row["builder"]
    if builder == "low_floral_centerpiece":
        build_low_floral(row)
        return
    if builder == "marigold_brass_cluster":
        build_marigold(row)
        return
    if builder == "mirror_welcome_sign":
        build_mirror(row)
        return
    raise RuntimeError(f"unknown builder {builder}")


def triangle_count(objects: list[bpy.types.Object]) -> int:
    total = 0
    for obj in objects:
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def decimate(objects: list[bpy.types.Object], budget: int) -> None:
    for _ in range(3):
        total = triangle_count(objects)
        if total <= budget:
            return
        ratio = max(0.05, min(0.92, budget / max(total, 1) * 0.84))
        for obj in objects:
            obj.data.calc_loop_triangles()
            if len(obj.data.loop_triangles) < 120:
                continue
            modifier = obj.modifiers.new("BS_LOD0", "DECIMATE")
            modifier.ratio = ratio
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            obj.select_set(False)
        bpy.context.view_layer.update()
    if triangle_count(objects) > budget:
        raise RuntimeError(f"decimation could not meet triangle budget {budget}")


def source_ids(row: dict[str, str]) -> list[str]:
    return [row.get(key, "").strip() for key in ("primary_source_id", "secondary_source_id", "tertiary_source_id") if row.get(key, "").strip()]


def export_asset(row: dict[str, str], manifest_row: dict[str, str]) -> dict[str, object]:
    expected = (float(manifest_row["width_m"]), float(manifest_row["depth_m"]), float(manifest_row["height_m"]))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    minimum, maximum = mesh_bounds(meshes)
    center = (minimum + maximum) / 2
    move(meshes, Vector((-center.x, -center.y, -minimum.z)))
    budget = int(manifest_row["lod0_triangle_budget"])
    decimate(meshes, budget)
    bpy.context.view_layer.update()
    minimum, maximum = mesh_bounds(meshes)
    actual = maximum - minimum
    for index, label in enumerate(("width", "depth", "height")):
        if actual[index] > expected[index] + 0.02:
            raise RuntimeError(f"{label} {actual[index]:.4f} exceeds placement envelope {expected[index]:.4f}")
        if actual[index] < expected[index] * 0.60:
            raise RuntimeError(f"{label} {actual[index]:.4f} is grossly undersized for placement envelope {expected[index]:.4f}")
    triangles = triangle_count(meshes)
    if triangles > budget:
        raise RuntimeError(f"triangle budget exceeded: {triangles}")
    root = bpy.data.objects.new("BS_ROOT", None)
    bpy.context.collection.objects.link(root)
    for obj in meshes:
        obj.parent = root
    ids = source_ids(row)
    if not ids:
        raise RuntimeError(f"{row['asset_id']} has no provenance source ids")
    root["bakesmart_asset_id"] = manifest_row["asset_id"]
    root["bakesmart_catalog_id"] = manifest_row["catalog_id"]
    root["bakesmart_units"] = "metres"
    root["bakesmart_dimensions_m"] = list(expected)
    root["bakesmart_visible_mesh_bounds_m"] = [float(value) for value in actual]
    root["bakesmart_anchor_type"] = manifest_row["anchor_type"]
    root["bakesmart_scaling_policy"] = manifest_row["scaling_policy"]
    root["bakesmart_manifest_version"] = "production-assets-v1"
    root["bakesmart_review_only"] = True
    root["bakesmart_source_license"] = "cc0_confirmed"
    root["bakesmart_source_ids"] = ids
    root["bakesmart_local_authored_geometry"] = row["builder"] in {"low_floral_centerpiece", "marigold_brass_cluster"}
    output = ROOT / manifest_row["glb_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_extras=True, export_apply=True, export_yup=True, export_materials="EXPORT")
    return {
        "asset_id": row["asset_id"],
        "output": str(output.relative_to(ROOT)),
        "source_ids": ids,
        "source_license_status": "cc0_confirmed",
        "redistribution_allowed": True,
        "true_dimensions_m": [round(float(value), 4) for value in expected],
        "visible_mesh_bounds_m": [round(float(value), 4) for value in actual],
        "triangle_count": triangles,
        "status": "built_for_final_visual_review",
    }


def main() -> int:
    arguments = parse_args()
    plan = read_rows(arguments.plan)
    manifest = {row["asset_id"]: row for row in read_rows(MANIFEST)}
    chosen = set(arguments.asset_id or [])
    results: list[dict[str, object]] = []
    for row in plan:
        if chosen and row["asset_id"] not in chosen:
            continue
        if row["source_license_status"] != "cc0_confirmed":
            raise RuntimeError(f"{row['asset_id']} is not CC0-confirmed")
        if row["redistribution_allowed"].strip().lower() != "true":
            raise RuntimeError(f"{row['asset_id']} is not redistributable")
        if row["asset_id"] not in manifest:
            raise RuntimeError(f"{row['asset_id']} missing from production manifest")
        clear_scene()
        build(row)
        result = export_asset(row, manifest[row["asset_id"]])
        results.append(result)
        print(json.dumps(result, indent=2))
    if not results:
        raise RuntimeError("no assets selected")
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(json.dumps({
        "report_version": "production-candidate-build-v2",
        "review_only": True,
        "production_ready": False,
        "assets": results,
        "note": "Automated structural validation and final human visual QA are required before production_ready.",
    }, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
