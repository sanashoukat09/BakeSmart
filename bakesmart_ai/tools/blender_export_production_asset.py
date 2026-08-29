"""Blender-side BakeSmart production GLB exporter.

Run with Blender, not normal Python:
    blender --background source.blend --python tools/blender_export_production_asset.py \
      -- --asset-id prod-backdrop-round-arch

The .blend file must contain a root object named BS_ROOT. The combined evaluated
mesh bounds must match the manifest's true-size dimensions within 2 cm.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE_ROOT / "data" / "production_assets_v1" / "asset_manifest.csv"


def _arguments() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def _manifest_row(asset_id: str) -> dict[str, str]:
    with MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["asset_id"] == asset_id:
            return row
    raise SystemExit(f"Unknown production asset: {asset_id}")


def _mesh_objects() -> list:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def _triangle_count() -> int:
    total = 0
    for obj in _mesh_objects():
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def _combined_world_dimensions() -> tuple[float, float, float]:
    mesh_objects = _mesh_objects()
    if not mesh_objects:
        raise SystemExit("No mesh objects are present.")
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in mesh_objects
        for corner in obj.bound_box
    ]
    minimum = tuple(min(point[index] for point in points) for index in range(3))
    maximum = tuple(max(point[index] for point in points) for index in range(3))
    return tuple(maximum[index] - minimum[index] for index in range(3))


def _validate_materials() -> None:
    mesh_objects = _mesh_objects()
    if not mesh_objects:
        raise SystemExit("No mesh objects are present.")
    for obj in mesh_objects:
        if not obj.data.materials:
            raise SystemExit(f"{obj.name} has no material.")
        for material in obj.data.materials:
            if material is None or not material.use_nodes:
                raise SystemExit(f"{obj.name} must use node-based PBR materials.")
            principled = [
                node
                for node in material.node_tree.nodes
                if node.type == "BSDF_PRINCIPLED"
            ]
            if not principled:
                raise SystemExit(
                    f"{obj.name}/{material.name} has no Principled BSDF node."
                )


def _apply_mesh_scales() -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in _mesh_objects():
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.select_set(False)


def main() -> None:
    args = _arguments()
    row = _manifest_row(args.asset_id)
    root = bpy.data.objects.get("BS_ROOT")
    if root is None:
        raise SystemExit("Required root object BS_ROOT was not found.")

    _apply_mesh_scales()
    bpy.context.view_layer.update()

    expected = (
        float(row["width_m"]),
        float(row["depth_m"]),
        float(row["height_m"]),
    )
    actual = _combined_world_dimensions()
    for axis, (measured, target) in zip("XYZ", zip(actual, expected, strict=True), strict=True):
        if abs(measured - target) > 0.02:
            raise SystemExit(
                f"Combined mesh {axis} dimension {measured:.3f} m does not match "
                f"manifest target {target:.3f} m within 2 cm."
            )

    _validate_materials()
    triangles = _triangle_count()
    budget = int(row["lod0_triangle_budget"])
    if triangles > budget:
        raise SystemExit(
            f"Triangle count {triangles} exceeds LOD0 budget {budget}."
        )

    root["bakesmart_asset_id"] = row["asset_id"]
    root["bakesmart_catalog_id"] = row["catalog_id"]
    root["bakesmart_units"] = "metres"
    root["bakesmart_dimensions_m"] = list(expected)
    root["bakesmart_anchor_type"] = row["anchor_type"]
    root["bakesmart_scaling_policy"] = row["scaling_policy"]
    root["bakesmart_manifest_version"] = "production-assets-v1"

    output = Path(args.output) if args.output else PACKAGE_ROOT / row["glb_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_extras=True,
        export_apply=True,
        export_yup=True,
        export_materials="EXPORT",
    )
    print(
        f"Exported {row['asset_id']} -> {output} "
        f"({triangles} triangles, true size {expected} m)"
    )


if __name__ == "__main__":
    main()
