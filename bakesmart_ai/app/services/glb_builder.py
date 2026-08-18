"""Deterministic procedural glTF 2.0 binary scene generation for BakeSmart."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from typing import Iterable

from app.schemas.design import (
    CakePlacement,
    DesignRequest,
    Dimensions,
    ObjectPlacement,
    SceneSpecification,
)


Color = tuple[float, float, float]
Vector3 = tuple[float, float, float]

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK_TYPE = 0x4E4F534A
BIN_CHUNK_TYPE = 0x004E4942
FLOAT_COMPONENT = 5126
UNSIGNED_SHORT_COMPONENT = 5123
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


@dataclass(frozen=True)
class GeneratedGlb:
    data: bytes
    vertex_count: int
    triangle_count: int
    bounds_min: Vector3
    bounds_max: Vector3


@dataclass
class MeshAccumulator:
    positions: list[float] = field(default_factory=list)
    normals: list[float] = field(default_factory=list)
    colors: list[float] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        return len(self.positions) // 3

    def _vertex(self, position: Vector3, normal: Vector3, color: Color) -> int:
        index = self.vertex_count
        self.positions.extend(position)
        self.normals.extend(normal)
        self.colors.extend(color)
        return index

    def add_box(self, center: Vector3, size: Vector3, color: Color) -> None:
        half_x, half_y, half_z = (value / 2 for value in size)
        cx, cy, cz = center
        faces = (
            (
                (1.0, 0.0, 0.0),
                (
                    (half_x, -half_y, -half_z),
                    (half_x, -half_y, half_z),
                    (half_x, half_y, half_z),
                    (half_x, half_y, -half_z),
                ),
            ),
            (
                (-1.0, 0.0, 0.0),
                (
                    (-half_x, -half_y, half_z),
                    (-half_x, -half_y, -half_z),
                    (-half_x, half_y, -half_z),
                    (-half_x, half_y, half_z),
                ),
            ),
            (
                (0.0, 1.0, 0.0),
                (
                    (-half_x, half_y, -half_z),
                    (half_x, half_y, -half_z),
                    (half_x, half_y, half_z),
                    (-half_x, half_y, half_z),
                ),
            ),
            (
                (0.0, -1.0, 0.0),
                (
                    (-half_x, -half_y, half_z),
                    (half_x, -half_y, half_z),
                    (half_x, -half_y, -half_z),
                    (-half_x, -half_y, -half_z),
                ),
            ),
            (
                (0.0, 0.0, 1.0),
                (
                    (half_x, -half_y, half_z),
                    (-half_x, -half_y, half_z),
                    (-half_x, half_y, half_z),
                    (half_x, half_y, half_z),
                ),
            ),
            (
                (0.0, 0.0, -1.0),
                (
                    (-half_x, -half_y, -half_z),
                    (half_x, -half_y, -half_z),
                    (half_x, half_y, -half_z),
                    (-half_x, half_y, -half_z),
                ),
            ),
        )
        for normal, offsets in faces:
            start = self.vertex_count
            for x, y, z in offsets:
                self._vertex((cx + x, cy + y, cz + z), normal, color)
            self.indices.extend(
                (start, start + 1, start + 2, start, start + 2, start + 3)
            )

    def add_cylinder(
        self,
        center: Vector3,
        radius: float,
        height: float,
        color: Color,
        segments: int = 24,
    ) -> None:
        cx, cy, cz = center
        lower = cy - height / 2
        upper = cy + height / 2
        for segment in range(segments):
            angle_one = 2 * math.pi * segment / segments
            angle_two = 2 * math.pi * (segment + 1) / segments
            x_one, z_one = math.cos(angle_one), math.sin(angle_one)
            x_two, z_two = math.cos(angle_two), math.sin(angle_two)

            side_start = self.vertex_count
            self._vertex(
                (cx + radius * x_one, lower, cz + radius * z_one),
                (x_one, 0.0, z_one),
                color,
            )
            self._vertex(
                (cx + radius * x_two, lower, cz + radius * z_two),
                (x_two, 0.0, z_two),
                color,
            )
            self._vertex(
                (cx + radius * x_two, upper, cz + radius * z_two),
                (x_two, 0.0, z_two),
                color,
            )
            self._vertex(
                (cx + radius * x_one, upper, cz + radius * z_one),
                (x_one, 0.0, z_one),
                color,
            )
            self.indices.extend(
                (
                    side_start,
                    side_start + 1,
                    side_start + 2,
                    side_start,
                    side_start + 2,
                    side_start + 3,
                )
            )

            top_start = self.vertex_count
            self._vertex((cx, upper, cz), (0.0, 1.0, 0.0), color)
            self._vertex(
                (cx + radius * x_one, upper, cz + radius * z_one),
                (0.0, 1.0, 0.0),
                color,
            )
            self._vertex(
                (cx + radius * x_two, upper, cz + radius * z_two),
                (0.0, 1.0, 0.0),
                color,
            )
            self.indices.extend((top_start, top_start + 1, top_start + 2))

            bottom_start = self.vertex_count
            self._vertex((cx, lower, cz), (0.0, -1.0, 0.0), color)
            self._vertex(
                (cx + radius * x_two, lower, cz + radius * z_two),
                (0.0, -1.0, 0.0),
                color,
            )
            self._vertex(
                (cx + radius * x_one, lower, cz + radius * z_one),
                (0.0, -1.0, 0.0),
                color,
            )
            self.indices.extend((bottom_start, bottom_start + 1, bottom_start + 2))

    def add_sphere(
        self,
        center: Vector3,
        radius: float,
        color: Color,
        latitude_segments: int = 8,
        longitude_segments: int = 12,
    ) -> None:
        cx, cy, cz = center
        start = self.vertex_count
        for latitude in range(latitude_segments + 1):
            phi = math.pi * latitude / latitude_segments
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)
            for longitude in range(longitude_segments + 1):
                theta = 2 * math.pi * longitude / longitude_segments
                normal = (
                    sin_phi * math.cos(theta),
                    cos_phi,
                    sin_phi * math.sin(theta),
                )
                self._vertex(
                    (
                        cx + radius * normal[0],
                        cy + radius * normal[1],
                        cz + radius * normal[2],
                    ),
                    normal,
                    color,
                )
        row_length = longitude_segments + 1
        for latitude in range(latitude_segments):
            for longitude in range(longitude_segments):
                first = start + latitude * row_length + longitude
                second = first + row_length
                self.indices.extend(
                    (first, second, first + 1, second, second + 1, first + 1)
                )


class ProceduralGlbBuilder:
    """Create a compact, colored GLB containing every recommended scene layer."""

    def build(
        self,
        request: DesignRequest,
        scene: SceneSpecification,
        cake: CakePlacement,
        palette_hex: str,
        design_id: str,
    ) -> GeneratedGlb:
        palette = self._palette(palette_hex)
        mesh = MeshAccumulator()
        width = request.space.dimensions.width_m
        depth = request.space.dimensions.depth_m or 2.0
        mesh.add_box(
            (0.0, -0.025, 0.0),
            (width, 0.05, depth),
            self._mix(palette[-1], (0.75, 0.77, 0.8), 0.65),
        )

        for placement in scene.objects:
            self._add_placement(
                mesh,
                placement,
                cake,
                palette,
                width,
                depth,
            )
        if mesh.vertex_count > 65_535:
            raise ValueError("procedural scene exceeds the 16-bit viewer vertex limit")
        return self._encode(mesh, design_id, scene.layers)

    def _add_placement(
        self,
        mesh: MeshAccumulator,
        placement: ObjectPlacement,
        cake: CakePlacement,
        palette: list[Color],
        room_width: float,
        room_depth: float,
    ) -> None:
        dimensions = placement.dimensions or Dimensions(
            width_m=0.3,
            depth_m=0.3,
            height_m=0.3,
        )
        base = self._position(placement, room_width, room_depth)
        if placement.role == "cake_table":
            self._add_table(mesh, base, dimensions, palette)
        elif placement.role == "cake":
            self._add_cake(mesh, base, dimensions, cake, palette)
        elif placement.role == "backdrop":
            self._add_backdrop(mesh, base, dimensions, palette)
        elif placement.role == "lighting":
            self._add_light(mesh, base, dimensions, palette)
        elif placement.role == "signage":
            self._add_signage(mesh, base, dimensions, palette)
        elif "floor-arrangement" in placement.asset_id:
            self._add_floor_arrangement(mesh, base, dimensions, palette)
        else:
            self._add_table_decor(mesh, base, dimensions, palette)

    @staticmethod
    def _position(
        placement: ObjectPlacement,
        room_width: float,
        room_depth: float,
    ) -> Vector3:
        return (
            placement.position.x_m - room_width / 2,
            placement.position.z_m,
            placement.position.y_m - room_depth / 2,
        )

    @staticmethod
    def _add_table(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        palette: list[Color],
    ) -> None:
        depth = dimensions.depth_m or 0.75
        top_thickness = min(0.08, dimensions.height_m * 0.12)
        top_center = (
            base[0],
            base[1] + dimensions.height_m - top_thickness / 2,
            base[2],
        )
        mesh.add_box(
            top_center,
            (dimensions.width_m, top_thickness, depth),
            palette[-1],
        )
        leg_height = dimensions.height_m - top_thickness
        leg_width = min(0.08, dimensions.width_m * 0.1, depth * 0.1)
        for x_sign in (-1, 1):
            for z_sign in (-1, 1):
                mesh.add_box(
                    (
                        base[0]
                        + x_sign * (dimensions.width_m / 2 - leg_width),
                        base[1] + leg_height / 2,
                        base[2] + z_sign * (depth / 2 - leg_width),
                    ),
                    (leg_width, leg_height, leg_width),
                    ProceduralGlbBuilder._mix(palette[1], (0.35, 0.25, 0.2), 0.4),
                )

    @staticmethod
    def _add_cake(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        cake: CakePlacement,
        palette: list[Color],
    ) -> None:
        depth = dimensions.depth_m or dimensions.width_m
        tier_height = dimensions.height_m / cake.tiers
        for tier in range(cake.tiers):
            shrink = 1.0 - tier * 0.16
            center = (
                base[0],
                base[1] + tier * tier_height + tier_height / 2,
                base[2],
            )
            tier_color = ProceduralGlbBuilder._mix(
                palette[-1], palette[0], 0.12 * tier
            )
            if cake.shape.value in {"square", "rectangle"}:
                mesh.add_box(
                    center,
                    (
                        dimensions.width_m * shrink,
                        tier_height * 0.94,
                        depth * shrink,
                    ),
                    tier_color,
                )
            else:
                mesh.add_cylinder(
                    center,
                    max(0.02, dimensions.width_m * shrink / 2),
                    tier_height * 0.94,
                    tier_color,
                )
        topper_y = base[1] + dimensions.height_m + 0.025
        for offset in (-0.07, 0.0, 0.07):
            mesh.add_sphere(
                (base[0] + offset, topper_y + abs(offset) * 0.2, base[2]),
                max(0.025, min(dimensions.width_m, depth) * 0.08),
                palette[0],
            )

    @staticmethod
    def _add_backdrop(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        palette: list[Color],
    ) -> None:
        depth = dimensions.depth_m or 0.15
        column_width = max(0.05, dimensions.width_m * 0.05)
        mesh.add_box(
            (
                base[0],
                base[1] + dimensions.height_m / 2,
                base[2],
            ),
            (dimensions.width_m, dimensions.height_m, depth * 0.35),
            ProceduralGlbBuilder._mix(palette[0], palette[-1], 0.72),
        )
        for sign in (-1, 1):
            mesh.add_box(
                (
                    base[0]
                    + sign * (dimensions.width_m / 2 - column_width / 2),
                    base[1] + dimensions.height_m / 2,
                    base[2] + depth * 0.25,
                ),
                (column_width, dimensions.height_m, depth),
                palette[1],
            )
        mesh.add_box(
            (
                base[0],
                base[1] + dimensions.height_m - column_width / 2,
                base[2] + depth * 0.25,
            ),
            (dimensions.width_m, column_width, depth),
            palette[1],
        )

    @staticmethod
    def _add_floor_arrangement(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        palette: list[Color],
    ) -> None:
        depth = dimensions.depth_m or dimensions.width_m
        vase_height = dimensions.height_m * 0.42
        mesh.add_cylinder(
            (base[0], base[1] + vase_height / 2, base[2]),
            max(0.04, min(dimensions.width_m, depth) * 0.22),
            vase_height,
            palette[1],
            segments=16,
        )
        flower_y = base[1] + vase_height + dimensions.height_m * 0.18
        radius = max(0.04, min(dimensions.width_m, depth) * 0.24)
        for index, offset in enumerate(
            ((-0.12, 0.0), (0.0, 0.08), (0.12, 0.0), (-0.05, -0.08), (0.06, -0.08))
        ):
            mesh.add_sphere(
                (base[0] + offset[0], flower_y + abs(offset[0]) * 0.25, base[2] + offset[1]),
                radius,
                palette[index % len(palette)],
            )

    @staticmethod
    def _add_table_decor(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        palette: list[Color],
    ) -> None:
        depth = dimensions.depth_m or 0.25
        mesh.add_box(
            (
                base[0],
                base[1] + dimensions.height_m / 2,
                base[2],
            ),
            (dimensions.width_m, dimensions.height_m, depth),
            ProceduralGlbBuilder._mix(palette[0], palette[-1], 0.5),
        )
        for offset in (-0.2, 0.0, 0.2):
            mesh.add_sphere(
                (
                    base[0] + offset * dimensions.width_m,
                    base[1] + dimensions.height_m + 0.035,
                    base[2],
                ),
                max(0.02, dimensions.height_m * 0.3),
                palette[0],
            )

    @staticmethod
    def _add_light(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        palette: list[Color],
    ) -> None:
        radius = max(0.04, min(dimensions.width_m, dimensions.height_m) / 2)
        mesh.add_sphere(
            (base[0], base[1], base[2]),
            radius,
            ProceduralGlbBuilder._mix((1.0, 0.82, 0.38), palette[-1], 0.25),
        )

    @staticmethod
    def _add_signage(
        mesh: MeshAccumulator,
        base: Vector3,
        dimensions: Dimensions,
        palette: list[Color],
    ) -> None:
        depth = dimensions.depth_m or 0.12
        post_height = dimensions.height_m * 0.55
        mesh.add_cylinder(
            (base[0], base[1] + post_height / 2, base[2]),
            0.025,
            post_height,
            palette[1],
            segments=12,
        )
        mesh.add_box(
            (
                base[0],
                base[1] + dimensions.height_m * 0.75,
                base[2],
            ),
            (dimensions.width_m, dimensions.height_m * 0.45, depth),
            palette[-1],
        )

    @staticmethod
    def _palette(palette_hex: str) -> list[Color]:
        colors: list[Color] = []
        for value in palette_hex.split(";"):
            normalized = value.strip().lstrip("#")
            if len(normalized) != 6:
                continue
            colors.append(
                tuple(
                    int(normalized[index : index + 2], 16) / 255
                    for index in (0, 2, 4)
                )
            )
        return colors or [(0.9, 0.7, 0.75), (0.8, 0.7, 0.55), (0.98, 0.98, 0.96)]

    @staticmethod
    def _mix(first: Color, second: Color, amount: float) -> Color:
        clamped = min(max(amount, 0.0), 1.0)
        return tuple(
            first[index] * (1 - clamped) + second[index] * clamped
            for index in range(3)
        )

    @staticmethod
    def _encode(
        mesh: MeshAccumulator,
        design_id: str,
        layers: Iterable[str],
    ) -> GeneratedGlb:
        position_values = tuple(mesh.positions)
        normal_values = tuple(mesh.normals)
        color_values = tuple(mesh.colors)
        index_values = tuple(mesh.indices)
        if not position_values or not index_values:
            raise ValueError("cannot encode an empty procedural scene")

        position_bytes = struct.pack(f"<{len(position_values)}f", *position_values)
        normal_bytes = struct.pack(f"<{len(normal_values)}f", *normal_values)
        color_bytes = struct.pack(f"<{len(color_values)}f", *color_values)
        index_bytes = struct.pack(f"<{len(index_values)}H", *index_values)

        binary = bytearray()
        sections: list[tuple[int, int]] = []
        for values in (position_bytes, normal_bytes, color_bytes, index_bytes):
            while len(binary) % 4:
                binary.append(0)
            offset = len(binary)
            binary.extend(values)
            sections.append((offset, len(values)))
        binary_byte_length = len(binary)
        while len(binary) % 4:
            binary.append(0)

        triples = list(zip(*(iter(position_values),) * 3, strict=True))
        bounds_min = tuple(min(value[index] for value in triples) for index in range(3))
        bounds_max = tuple(max(value[index] for value in triples) for index in range(3))
        vertex_count = mesh.vertex_count
        document = {
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": FLOAT_COMPONENT,
                    "count": vertex_count,
                    "type": "VEC3",
                    "min": list(bounds_min),
                    "max": list(bounds_max),
                },
                {
                    "bufferView": 1,
                    "componentType": FLOAT_COMPONENT,
                    "count": vertex_count,
                    "type": "VEC3",
                },
                {
                    "bufferView": 2,
                    "componentType": FLOAT_COMPONENT,
                    "count": vertex_count,
                    "type": "VEC3",
                },
                {
                    "bufferView": 3,
                    "componentType": UNSIGNED_SHORT_COMPONENT,
                    "count": len(index_values),
                    "type": "SCALAR",
                    "min": [min(index_values)],
                    "max": [max(index_values)],
                },
            ],
            "asset": {
                "version": "2.0",
                "generator": "BakeSmart procedural GLB exporter",
                "extras": {
                    "design_id": design_id,
                    "layers": list(layers),
                    "units": "metres",
                    "procedural_concept": True,
                },
            },
            "buffers": [{"byteLength": binary_byte_length}],
            "bufferViews": [
                {
                    "buffer": 0,
                    "byteOffset": sections[0][0],
                    "byteLength": sections[0][1],
                    "target": ARRAY_BUFFER,
                },
                {
                    "buffer": 0,
                    "byteOffset": sections[1][0],
                    "byteLength": sections[1][1],
                    "target": ARRAY_BUFFER,
                },
                {
                    "buffer": 0,
                    "byteOffset": sections[2][0],
                    "byteLength": sections[2][1],
                    "target": ARRAY_BUFFER,
                },
                {
                    "buffer": 0,
                    "byteOffset": sections[3][0],
                    "byteLength": sections[3][1],
                    "target": ELEMENT_ARRAY_BUFFER,
                },
            ],
            "materials": [
                {
                    "name": "BakeSmart vertex colors",
                    "doubleSided": True,
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                        "metallicFactor": 0.0,
                        "roughnessFactor": 0.78,
                    },
                }
            ],
            "meshes": [
                {
                    "name": "BakeSmart combined event scene",
                    "primitives": [
                        {
                            "attributes": {
                                "POSITION": 0,
                                "NORMAL": 1,
                                "COLOR_0": 2,
                            },
                            "indices": 3,
                            "material": 0,
                            "mode": 4,
                        }
                    ],
                }
            ],
            "nodes": [{"mesh": 0, "name": design_id}],
            "scene": 0,
            "scenes": [{"nodes": [0], "name": "BakeSmart combined scene"}],
        }
        json_bytes = json.dumps(
            document,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        json_bytes += b" " * ((-len(json_bytes)) % 4)
        total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)
        output = bytearray()
        output.extend(struct.pack("<4sII", GLB_MAGIC, GLB_VERSION, total_length))
        output.extend(struct.pack("<II", len(json_bytes), JSON_CHUNK_TYPE))
        output.extend(json_bytes)
        output.extend(struct.pack("<II", len(binary), BIN_CHUNK_TYPE))
        output.extend(binary)
        return GeneratedGlb(
            bytes(output),
            vertex_count,
            len(index_values) // 3,
            bounds_min,
            bounds_max,
        )
