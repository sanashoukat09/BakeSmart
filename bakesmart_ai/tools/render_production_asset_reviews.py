"""Render all geometry-review production GLBs from fixed QA angles in Blender.

Run with Blender's Python:
  blender -b --python tools/render_production_asset_reviews.py -- --output-dir <dir>

This is deterministic visual-QA support. It never changes production status.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE_ROOT / "data" / "production_assets_v1" / "asset_manifest.csv"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def _mesh_bounds() -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        matrix = obj.matrix_world
        for corner in obj.bound_box:
            points.append(matrix @ Vector(corner))
    if not points:
        raise RuntimeError("Imported GLB contains no mesh bounds")
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return minimum, maximum


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _setup_world() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("ReviewWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.055, 0.055, 0.065, 1.0)
        background.inputs["Strength"].default_value = 0.45


def _add_floor(minimum: Vector, maximum: Vector) -> None:
    center = (minimum + maximum) * 0.5
    span = maximum - minimum
    size = max(span.x, span.y, 1.0) * 3.0
    bpy.ops.mesh.primitive_plane_add(size=size, location=(center.x, center.y, minimum.z - 0.004))
    floor = bpy.context.object
    floor.name = "QA_FLOOR"
    material = bpy.data.materials.new("QA_FLOOR_MAT")
    material.diffuse_color = (0.16, 0.16, 0.18, 1.0)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.16, 0.16, 0.18, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.82
    floor.data.materials.append(material)


def _add_lights(minimum: Vector, maximum: Vector) -> None:
    center = (minimum + maximum) * 0.5
    span = maximum - minimum
    radius = max(span.length, 1.0)
    for name, location, energy, size in (
        ("Key", center + Vector((radius * 1.4, -radius * 1.3, radius * 1.8)), 1000.0, radius * 1.6),
        ("Fill", center + Vector((-radius * 1.3, -radius * 0.3, radius * 1.1)), 550.0, radius * 1.3),
        ("Rim", center + Vector((0.0, radius * 1.5, radius * 1.7)), 750.0, radius * 1.1),
    ):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        _look_at(obj, center)


def _setup_camera(minimum: Vector, maximum: Vector) -> bpy.types.Object:
    data = bpy.data.cameras.new("QA_CAMERA")
    data.lens = 52
    camera = bpy.data.objects.new("QA_CAMERA", data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def _camera_location(center: Vector, span: Vector, azimuth_deg: float, elevation_deg: float) -> Vector:
    radius = max(span.length * 1.4, max(span.x, span.y, span.z) * 2.5, 1.0)
    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    horizontal = radius * math.cos(elevation)
    return center + Vector((
        horizontal * math.sin(azimuth),
        -horizontal * math.cos(azimuth),
        radius * math.sin(elevation),
    ))


def _configure_render() -> None:
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    look_items = {
        item.identifier
        for item in scene.bl_rna.properties["view_settings"].fixed_type.properties["look"].enum_items
    }
    for preferred in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        if preferred in look_items:
            scene.view_settings.look = preferred
            break


def render_asset(asset_id: str, glb_path: Path, output_dir: Path) -> None:
    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    minimum, maximum = _mesh_bounds()
    center = (minimum + maximum) * 0.5
    span = maximum - minimum
    _setup_world()
    _add_floor(minimum, maximum)
    _add_lights(minimum, maximum)
    camera = _setup_camera(minimum, maximum)
    _configure_render()

    angles = (
        ("front", 0.0, 12.0),
        ("front_right", 38.0, 18.0),
        ("side", 90.0, 14.0),
        ("top_oblique", -34.0, 42.0),
    )
    asset_dir = output_dir / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    for label, azimuth, elevation in angles:
        camera.location = _camera_location(center, span, azimuth, elevation)
        _look_at(camera, center)
        bpy.context.scene.render.filepath = str(asset_dir / f"{label}.png")
        bpy.ops.render.render(write_still=True)

    dimensions = maximum - minimum
    (asset_dir / "render_metrics.txt").write_text(
        "\n".join(
            [
                f"asset_id={asset_id}",
                f"bounds_min={minimum.x:.6f},{minimum.y:.6f},{minimum.z:.6f}",
                f"bounds_max={maximum.x:.6f},{maximum.y:.6f},{maximum.z:.6f}",
                f"dimensions_m={dimensions.x:.6f},{dimensions.y:.6f},{dimensions.z:.6f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    review_rows = [row for row in rows if row["production_status"] == "geometry_review"]
    if not review_rows:
        raise RuntimeError("No geometry_review assets were found in the manifest")
    for row in review_rows:
        glb_path = PACKAGE_ROOT / row["glb_path"]
        if not glb_path.is_file():
            raise FileNotFoundError(glb_path)
        print(f"Rendering {row['asset_id']} from {glb_path}")
        render_asset(row["asset_id"], glb_path, args.output_dir)
    print(f"Rendered {len(review_rows)} asset(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
