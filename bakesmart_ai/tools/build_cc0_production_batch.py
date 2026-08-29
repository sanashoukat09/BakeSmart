"""Build BakeSmart geometry-review GLBs from vetted CC0 source assets.

Run inside Blender. It does not call any AI service. Source files must already
have been downloaded by tools/collect_professional_assets.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path

import bpy
from mathutils import Vector


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = PACKAGE_ROOT / "data" / "production_assets_v1" / "production_batch1_plan.csv"
MANIFEST = PACKAGE_ROOT / "data" / "production_assets_v1" / "asset_manifest.csv"
RAW_ROOT = PACKAGE_ROOT / "assets" / "third_party_cc0" / "raw"
WORK_ROOT = PACKAGE_ROOT / "assets" / "third_party_cc0" / "working"
DEFAULT_REPORT = PACKAGE_ROOT / "data" / "production_assets_v1" / "production_candidate_build_report.json"


def _arguments() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--asset-id", action="append", dest="asset_ids")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _manifest_by_id() -> dict[str, dict[str, str]]:
    return {row["asset_id"]: row for row in _read_rows(MANIFEST)}


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _source_path(source_id: str) -> Path:
    source_dir = RAW_ROOT / source_id
    if not source_dir.is_dir():
        raise RuntimeError(f"Missing downloaded CC0 source directory: {source_dir}")
    archives = sorted(source_dir.glob("*.zip"))
    if archives:
        extract_dir = WORK_ROOT / source_id
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archives[0]) as archive:
            archive.extractall(extract_dir)
        candidates = sorted(extract_dir.rglob("*.glb")) + sorted(extract_dir.rglob("*.gltf"))
    else:
        candidates = sorted(source_dir.rglob("*.glb")) + sorted(source_dir.rglob("*.gltf"))
    if not candidates:
        raise RuntimeError(f"No GLB/glTF found for {source_id}")
    return candidates[0]


def _import_source(source_id: str, prefix: str) -> list[bpy.types.Object]:
    path = _source_path(source_id)
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    for obj in list(imported):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
            imported.remove(obj)
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"Imported source {source_id} contains no mesh objects")
    for index, obj in enumerate(meshes, start=1):
        obj.name = f"{prefix}_{index:02d}"
    return meshes


def _world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    minimum = Vector(tuple(min(point[i] for point in points) for i in range(3)))
    maximum = Vector(tuple(max(point[i] for point in points) for i in range(3)))
    return minimum, maximum


def _dimensions(objects: list[bpy.types.Object]) -> Vector:
    minimum, maximum = _world_bounds(objects)
    return maximum - minimum


def _move_group(objects: list[bpy.types.Object], delta: Vector) -> None:
    for obj in objects:
        obj.location += delta


def _scale_group_uniform(objects: list[bpy.types.Object], scale: float) -> None:
    minimum, _ = _world_bounds(objects)
    pivot = Vector((0.0, 0.0, minimum.z))
    for obj in objects:
        obj.location = pivot + (obj.location - pivot) * scale
        obj.scale *= scale


def _normalize_group(objects: list[bpy.types.Object]) -> None:
    minimum, maximum = _world_bounds(objects)
    center = (minimum + maximum) / 2
    _move_group(objects, Vector((-center.x, -center.y, -minimum.z)))


def _fit_group_uniform(objects: list[bpy.types.Object], max_width: float, max_depth: float, max_height: float, bottom_z: float) -> None:
    _normalize_group(objects)
    dims = _dimensions(objects)
    scale = min(max_width / max(dims.x, 1e-6), max_depth / max(dims.y, 1e-6), max_height / max(dims.z, 1e-6))
    _scale_group_uniform(objects, scale)
    minimum, maximum = _world_bounds(objects)
    center = (minimum + maximum) / 2
    _move_group(objects, Vector((-center.x, -center.y, bottom_z - minimum.z)))


def _fit_group_exact(objects: list[bpy.types.Object], width: float, depth: float, height: float, bottom_z: float) -> None:
    _normalize_group(objects)
    dims = _dimensions(objects)
    sx, sy, sz = width / max(dims.x, 1e-6), depth / max(dims.y, 1e-6), height / max(dims.z, 1e-6)
    for obj in objects:
        obj.location = Vector((obj.location.x * sx, obj.location.y * sy, obj.location.z * sz))
        obj.scale = Vector((obj.scale.x * sx, obj.scale.y * sy, obj.scale.z * sz))
    minimum, maximum = _world_bounds(objects)
    center = (minimum + maximum) / 2
    _move_group(objects, Vector((-center.x, -center.y, bottom_z - minimum.z)))


def _material(name: str, color: tuple[float, float, float, float], metallic: float, roughness: float) -> bpy.types.Material:
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    bsdf = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return material


def _add_cylinder(name: str, radius: float, depth: float, z: float, material: bpy.types.Material, vertices: int = 48) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def _add_cube(name: str, dimensions: tuple[float, float, float], location: tuple[float, float, float], material: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dimensions
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def _triangle_count(objects: list[bpy.types.Object]) -> int:
    total = 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def _decimate_to_budget(objects: list[bpy.types.Object], target: int) -> None:
    triangles = _triangle_count(objects)
    if triangles <= target or triangles <= 0:
        return
    ratio = max(0.08, min(1.0, target / triangles * 0.94))
    for obj in objects:
        if obj.type != "MESH":
            continue
        obj.data.calc_loop_triangles()
        if len(obj.data.loop_triangles) < 100:
            continue
        modifier = obj.modifiers.new(name="BakeSmart_LOD0_Decimate", type="DECIMATE")
        modifier.ratio = ratio
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(False)


def _build_low_floral(row: dict[str, str]) -> None:
    ceramic = _import_source(row["primary_source_id"], "CC0_CeramicVase")
    foliage = _import_source(row["secondary_source_id"], "CC0_FloralGreenery")
    ceramic_mat = _material("BS_CeramicBase", (0.92, 0.89, 0.82, 1.0), 0.0, 0.42)
    _add_cylinder("BS_CenterpiecePlate", 0.225, 0.025, 0.0125, ceramic_mat, vertices=64)
    _fit_group_uniform(ceramic, 0.18, 0.18, 0.14, 0.025)
    _fit_group_uniform(foliage, 0.45, 0.45, 0.16, 0.14)


def _build_marigold_cluster(row: dict[str, str]) -> None:
    brass = _import_source(row["primary_source_id"], "CC0_BrassVessel")
    flowers = _import_source(row["secondary_source_id"], "CC0_YellowFlowers")
    brass_mat = _material("BS_BrassClusterBase", (0.55, 0.30, 0.06, 1.0), 0.72, 0.28)
    _add_cylinder("BS_BrassFloorTray", 0.35, 0.03, 0.015, brass_mat, vertices=72)
    _fit_group_uniform(brass, 0.30, 0.30, 0.30, 0.03)
    _fit_group_uniform(flowers, 0.70, 0.70, 0.80, 0.30)


def _build_mirror_sign(row: dict[str, str]) -> None:
    mirror = _import_source(row["primary_source_id"], "CC0_OrnateMirrorFrame")
    metal = _material("BS_MirrorStandMetal", (0.68, 0.52, 0.20, 1.0), 0.65, 0.30)
    mirror_face = _material("BS_ReplaceableMirrorFace", (0.72, 0.78, 0.82, 1.0), 0.85, 0.12)
    _fit_group_exact(mirror, 0.70, 0.035, 1.30, 0.18)
    _add_cube("BS_MirrorFace", (0.54, 0.012, 1.08), (0.0, -0.006, 0.82), mirror_face)
    _add_cube("BS_StandBase", (0.75, 0.05, 0.05), (0.0, 0.0, 0.025), metal)
    _add_cube("BS_StandStemL", (0.025, 0.04, 0.18), (-0.31, 0.0, 0.115), metal)
    _add_cube("BS_StandStemR", (0.025, 0.04, 0.18), (0.31, 0.0, 0.115), metal)


BUILDERS = {
    "low_floral_centerpiece": _build_low_floral,
    "marigold_brass_cluster": _build_marigold_cluster,
    "mirror_welcome_sign": _build_mirror_sign,
}


def _combined_dimensions() -> tuple[float, float, float]:
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    minimum, maximum = _world_bounds(objects)
    dims = maximum - minimum
    return (float(dims.x), float(dims.y), float(dims.z))


def _anchor_scene() -> None:
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    minimum, maximum = _world_bounds(objects)
    center = (minimum + maximum) / 2
    _move_group(objects, Vector((-center.x, -center.y, -minimum.z)))


def _export(row: dict[str, str], manifest: dict[str, str]) -> dict[str, object]:
    root = bpy.data.objects.new("BS_ROOT", None)
    bpy.context.collection.objects.link(root)
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    _anchor_scene()
    budget = int(manifest["lod0_triangle_budget"])
    _decimate_to_budget(mesh_objects, max(100, budget - 500))
    bpy.context.view_layer.update()
    expected = (float(manifest["width_m"]), float(manifest["depth_m"]), float(manifest["height_m"]))
    actual = _combined_dimensions()
    if any(abs(a - b) > 0.02 for a, b in zip(actual, expected)):
        raise RuntimeError(f"{row['asset_id']} authored dimensions {actual} do not match target {expected} within 2 cm")
    for obj in mesh_objects:
        obj.parent = root
    triangles = _triangle_count(mesh_objects)
    if triangles > budget:
        raise RuntimeError(f"{row['asset_id']} triangle count {triangles} exceeds budget {budget}")
    root["bakesmart_asset_id"] = manifest["asset_id"]
    root["bakesmart_catalog_id"] = manifest["catalog_id"]
    root["bakesmart_units"] = "metres"
    root["bakesmart_dimensions_m"] = list(expected)
    root["bakesmart_anchor_type"] = manifest["anchor_type"]
    root["bakesmart_scaling_policy"] = manifest["scaling_policy"]
    root["bakesmart_manifest_version"] = "production-assets-v1"
    root["bakesmart_review_only"] = True
    root["bakesmart_source_license"] = row["source_license_status"]
    root["bakesmart_primary_source_id"] = row["primary_source_id"]
    if row.get("secondary_source_id"):
        root["bakesmart_secondary_source_id"] = row["secondary_source_id"]
    output = PACKAGE_ROOT / manifest["glb_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_extras=True, export_apply=True, export_yup=True, export_materials="EXPORT")
    return {
        "asset_id": row["asset_id"],
        "output": str(output.relative_to(PACKAGE_ROOT)),
        "source_ids": [s for s in (row["primary_source_id"], row.get("secondary_source_id", "")) if s],
        "source_license_status": row["source_license_status"],
        "redistribution_allowed": row["redistribution_allowed"] == "true",
        "true_dimensions_m": [round(v, 4) for v in actual],
        "triangle_count": triangles,
        "status": "built_for_geometry_review",
    }


def main() -> None:
    args = _arguments()
    plan = _read_rows(args.plan)
    manifest = _manifest_by_id()
    selected = set(args.asset_ids or [])
    results: list[dict[str, object]] = []
    for row in plan:
        if selected and row["asset_id"] not in selected:
            continue
        if row["source_license_status"] != "cc0_confirmed" or row["redistribution_allowed"] != "true":
            raise RuntimeError(f"Rights gate failed for {row['asset_id']}")
        manifest_row = manifest.get(row["asset_id"])
        if manifest_row is None:
            raise RuntimeError(f"Unknown production asset id: {row['asset_id']}")
        builder = BUILDERS.get(row["builder"])
        if builder is None:
            raise RuntimeError(f"Unknown builder: {row['builder']}")
        _clear_scene()
        builder(row)
        results.append(_export(row, manifest_row))
        print(json.dumps(results[-1], indent=2))
    if not results:
        raise RuntimeError("No production candidates were selected")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "report_version": "production-candidate-build-v1",
        "review_only": True,
        "production_ready": False,
        "assets": results,
        "note": "These GLBs are structural/material candidates only. Human visual review is required before production_ready."
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
