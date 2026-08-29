"""Deterministic local GLB geometry for BakeSmart's professional review slices.

These binaries are generated from source on demand and remain review-only. They
are not production-manifest files and are never promoted to customer-renderable
assets by this module.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetSpec:
    asset_id: str
    catalog_id: str
    recipe: str
    width_m: float
    depth_m: float
    height_m: float
    anchor_type: str
    base_color: tuple[float, float, float, float]
    metallic: float
    roughness: float


SPECS = (
    AssetSpec("prod-backdrop-chiara-panels", "backdrop-chiara-panels", "chiara", 2.60, 0.65, 2.20, "wall_floor_center", (0.94, 0.78, 0.84, 1.0), 0.0, 0.62),
    AssetSpec("prod-floor-balloon-clusters", "floor-balloon-clusters", "balloons", 0.65, 0.65, 1.40, "floor_center", (0.96, 0.62, 0.72, 1.0), 0.0, 0.35),
    AssetSpec("prod-lighting-curtain", "lighting-curtain", "light_curtain", 3.00, 0.08, 2.50, "wall_center", (1.0, 0.78, 0.35, 1.0), 0.05, 0.30),
    AssetSpec("prod-sign-foamboard-welcome", "sign-foamboard-welcome", "foam_sign", 0.60, 0.04, 0.90, "floor_center", (0.96, 0.78, 0.84, 1.0), 0.0, 0.65),
    AssetSpec("prod-backdrop-floral-arch", "backdrop-floral-arch", "floral_arch", 2.80, 0.90, 2.50, "wall_floor_center", (0.96, 0.82, 0.82, 1.0), 0.05, 0.58),
    AssetSpec("prod-floor-floral-pedestal-pair", "floor-floral-pedestal-pair", "floral_pedestal", 0.55, 0.55, 1.50, "floor_center", (0.95, 0.78, 0.80, 1.0), 0.05, 0.55),
    AssetSpec("prod-table-low-floral", "table-low-floral", "low_floral", 0.45, 0.45, 0.30, "surface_center", (0.95, 0.78, 0.80, 1.0), 0.0, 0.62),
    AssetSpec("prod-lighting-led-candles", "lighting-led-candles", "candles", 0.08, 0.08, 0.18, "surface_center", (1.0, 0.78, 0.42, 1.0), 0.0, 0.40),
    AssetSpec("prod-backdrop-south-asian-stage", "backdrop-south-asian-stage", "mehndi_stage", 5.00, 1.80, 3.00, "wall_floor_center", (0.95, 0.55, 0.16, 1.0), 0.10, 0.55),
    AssetSpec("prod-floor-marigold-clusters", "floor-marigold-clusters", "marigold", 0.70, 0.70, 1.10, "floor_center", (1.0, 0.68, 0.04, 1.0), 0.05, 0.55),
    AssetSpec("prod-table-mehndi-textile", "table-mehndi-textile", "mehndi_table", 0.90, 0.90, 0.35, "surface_center", (0.90, 0.42, 0.18, 1.0), 0.20, 0.50),
    AssetSpec("prod-lighting-festoon", "lighting-festoon", "festoon", 10.00, 0.06, 0.06, "overhead_center", (1.0, 0.72, 0.25, 1.0), 0.05, 0.30),
)


class Mesh:
    def __init__(self) -> None:
        self.positions: list[tuple[float, float, float]] = []
        self.normals: list[tuple[float, float, float]] = []
        self.colors: list[tuple[float, float, float]] = []
        self.indices: list[int] = []

    def vertex(self, position, normal, color) -> int:
        self.positions.append(tuple(float(value) for value in position))
        self.normals.append(tuple(float(value) for value in normal))
        self.colors.append(tuple(float(value) for value in color))
        return len(self.positions) - 1

    def box(self, center, size, color) -> None:
        cx, cy, cz = center
        sx, sy, sz = size
        x0, x1 = cx - sx / 2, cx + sx / 2
        y0, y1 = cy - sy / 2, cy + sy / 2
        z0, z1 = cz - sz / 2, cz + sz / 2
        faces = (
            ((1, 0, 0), ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))),
            ((-1, 0, 0), ((x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x0, y0, z0))),
            ((0, 1, 0), ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0))),
            ((0, -1, 0), ((x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1))),
            ((0, 0, 1), ((x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1))),
            ((0, 0, -1), ((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))),
        )
        for normal, points in faces:
            base = [self.vertex(point, normal, color) for point in points]
            self.indices.extend((base[0], base[1], base[2], base[0], base[2], base[3]))

    def sphere(self, center, radii, color, segments=10, rings=6) -> None:
        cx, cy, cz = center
        rx, ry, rz = radii
        base = len(self.positions)
        for ring in range(rings + 1):
            phi = math.pi * ring / rings
            sin_phi, cos_phi = math.sin(phi), math.cos(phi)
            for segment in range(segments + 1):
                theta = 2 * math.pi * segment / segments
                sin_theta, cos_theta = math.sin(theta), math.cos(theta)
                position = (
                    cx + rx * sin_phi * cos_theta,
                    cy + ry * cos_phi,
                    cz + rz * sin_phi * sin_theta,
                )
                normal = (
                    sin_phi * cos_theta / max(rx, 1e-6),
                    cos_phi / max(ry, 1e-6),
                    sin_phi * sin_theta / max(rz, 1e-6),
                )
                length = math.sqrt(sum(value * value for value in normal)) or 1.0
                self.vertex(position, tuple(value / length for value in normal), color)
        for ring in range(rings):
            for segment in range(segments):
                a = base + ring * (segments + 1) + segment
                b = a + segments + 1
                self.indices.extend((a, b, a + 1, a + 1, b, b + 1))

    def cylinder(self, start, end, radius, color, segments=10) -> None:
        x0, y0, z0 = start
        x1, y1, z1 = end
        axis = (x1 - x0, y1 - y0, z1 - z0)
        length = math.sqrt(sum(value * value for value in axis))
        if length < 1e-8:
            return
        w = tuple(value / length for value in axis)
        ref = (0, 1, 0) if abs(w[1]) < 0.9 else (1, 0, 0)
        u = (
            ref[1] * w[2] - ref[2] * w[1],
            ref[2] * w[0] - ref[0] * w[2],
            ref[0] * w[1] - ref[1] * w[0],
        )
        u_length = math.sqrt(sum(value * value for value in u))
        u = tuple(value / u_length for value in u)
        v = (
            w[1] * u[2] - w[2] * u[1],
            w[2] * u[0] - w[0] * u[2],
            w[0] * u[1] - w[1] * u[0],
        )
        ring0, ring1 = [], []
        for index in range(segments):
            angle = 2 * math.pi * index / segments
            c, s = math.cos(angle), math.sin(angle)
            normal = tuple(u[i] * c + v[i] * s for i in range(3))
            ring0.append(self.vertex(tuple(start[i] + radius * normal[i] for i in range(3)), normal, color))
            ring1.append(self.vertex(tuple(end[i] + radius * normal[i] for i in range(3)), normal, color))
        for index in range(segments):
            nxt = (index + 1) % segments
            self.indices.extend((ring0[index], ring1[index], ring1[nxt], ring0[index], ring1[nxt], ring0[nxt]))

    def fit_bounds(self, width: float, depth: float, height: float) -> None:
        mins = [min(point[index] for point in self.positions) for index in range(3)]
        maxs = [max(point[index] for point in self.positions) for index in range(3)]
        targets = ((-width / 2, width / 2), (0.0, height), (-depth / 2, depth / 2))
        scales = [
            (targets[index][1] - targets[index][0]) / (maxs[index] - mins[index])
            for index in range(3)
        ]
        self.positions = [
            tuple(
                targets[index][0] + (point[index] - mins[index]) * scales[index]
                for index in range(3)
            )
            for point in self.positions
        ]
        transformed = []
        for normal in self.normals:
            values = [normal[index] / scales[index] for index in range(3)]
            length = math.sqrt(sum(value * value for value in values)) or 1.0
            transformed.append(tuple(value / length for value in values))
        self.normals = transformed


def _recipe(spec: AssetSpec) -> Mesh:
    mesh = Mesh()
    w, d, h = spec.width_m, spec.depth_m, spec.height_m
    if spec.recipe == "chiara":
        colors = ((0.95, 0.76, 0.82), (0.98, 0.90, 0.75), (0.86, 0.80, 0.93))
        for x, panel_w, panel_h, color in zip((-0.78, 0, 0.78), (0.9, 1.0, 0.9), (1.82, 2.2, 1.9), colors, strict=True):
            mesh.box((x, panel_h / 2, 0), (panel_w, panel_h, 0.09), color)
            mesh.box((x, 0.035, 0), (0.38, 0.07, d), (0.65, 0.58, 0.52))
    elif spec.recipe == "balloons":
        mesh.box((0, 0.04, 0), (w, 0.08, d), (0.35, 0.28, 0.33))
        palette = ((0.96, 0.62, 0.72), (0.96, 0.82, 0.42), (0.62, 0.79, 0.96), (0.76, 0.62, 0.92))
        points = ((-0.20, 0.30, -0.05), (0.16, 0.35, 0.02), (-0.10, 0.58, 0.04), (0.20, 0.72, -0.08), (-0.19, 0.91, 0.05), (0.12, 1.08, 0), (0, 1.25, 0.03))
        for index, point in enumerate(points):
            radius = 0.14 if index < 5 else 0.12
            mesh.sphere(point, (radius, radius * 1.15, radius), palette[index % len(palette)])
        mesh.cylinder((0, 0.06, 0), (0, 1.38, 0), 0.018, (0.45, 0.45, 0.48), 8)
    elif spec.recipe == "light_curtain":
        warm = (1.0, 0.78, 0.35)
        mesh.cylinder((-w / 2, h, 0), (w / 2, h, 0), 0.008, (0.32, 0.28, 0.25), 6)
        for index in range(13):
            x = -w / 2 + w * index / 12
            mesh.cylinder((x, h, 0), (x, 0.04, 0), 0.004, (0.35, 0.30, 0.24), 6)
            for light in range(9):
                y = 0.16 + (h - 0.25) * light / 8
                mesh.sphere((x, y, 0), (0.025, 0.035, 0.025), warm, 8, 5)
        mesh.box((0, 0.01, 0), (w, 0.02, d), (0.20, 0.18, 0.18))
    elif spec.recipe == "foam_sign":
        board_h, board_y = 0.64, 0.58
        mesh.box((0, board_y, 0), (w, board_h, d), (0.96, 0.78, 0.84))
        mesh.box((0, board_y, -d / 2 + 0.003), (w * 0.72, board_h * 0.62, 0.006), (0.99, 0.94, 0.90))
        mesh.cylinder((-w * 0.28, 0, 0), (-w * 0.12, 0.28, 0), 0.015, (0.48, 0.31, 0.20), 8)
        mesh.cylinder((w * 0.28, 0, 0), (w * 0.12, 0.28, 0), 0.015, (0.48, 0.31, 0.20), 8)
        mesh.cylinder((0, 0, 0), (0, h, 0), 0.012, (0.48, 0.31, 0.20), 8)
    elif spec.recipe == "floral_arch":
        metal, green, blush, ivory = (0.78, 0.70, 0.48), (0.22, 0.46, 0.24), (0.95, 0.67, 0.73), (0.96, 0.93, 0.83)
        left, right = -w / 2 + 0.18, w / 2 - 0.18
        mesh.cylinder((left, 0, 0), (left, h * 0.72, 0), 0.035, metal)
        mesh.cylinder((right, 0, 0), (right, h * 0.72, 0), 0.035, metal)
        points = []
        for index in range(13):
            angle = math.pi - math.pi * index / 12
            points.append(((right - left) / 2 * math.cos(angle), h * 0.72 + h * 0.28 * math.sin(angle), 0))
        for start, end in zip(points, points[1:]):
            mesh.cylinder(start, end, 0.035, metal)
        for index, (x, y) in enumerate(((-1.05, 1.62), (-0.86, 1.94), (-0.55, 2.20), (-0.18, 2.38), (0.20, 2.43), (0.55, 2.30), (0.86, 2.05))):
            mesh.sphere((x, y, 0.03), (0.20, 0.16, 0.13), green)
            mesh.sphere((x - 0.06, y + 0.02, -0.03), (0.08, 0.07, 0.07), blush if index % 2 == 0 else ivory, 8, 5)
        mesh.box((left, 0.04, 0), (0.35, 0.08, d), metal)
        mesh.box((right, 0.04, 0), (0.35, 0.08, d), metal)
    elif spec.recipe == "floral_pedestal":
        metal, green, floral = (0.72, 0.64, 0.52), (0.20, 0.42, 0.22), (0.96, 0.76, 0.78)
        mesh.box((0, 0.03, 0), (w, 0.06, d), metal)
        mesh.cylinder((0, 0.06, 0), (0, h * 0.70, 0), 0.035, metal)
        for index in range(9):
            angle = 2 * math.pi * index / 9
            x, z = 0.17 * math.cos(angle), 0.17 * math.sin(angle)
            y = h * 0.78 + 0.10 * math.sin(2 * angle)
            mesh.sphere((x, y, z), (0.13, 0.11, 0.12), green, 9, 5)
            mesh.sphere((x * 0.8, y + 0.05, z * 0.8), (0.065, 0.055, 0.06), floral if index % 2 else (0.96, 0.91, 0.82), 8, 5)
        mesh.sphere((0, h - 0.08, 0), (0.20, 0.08, 0.18), green, 10, 5)
    elif spec.recipe == "low_floral":
        mesh.sphere((0, 0.10, 0), (w * 0.22, 0.10, d * 0.22), (0.88, 0.82, 0.75))
        for index in range(14):
            angle = 2 * math.pi * index / 14
            radius = 0.08 + 0.11 * (index % 3) / 2
            mesh.sphere((radius * math.cos(angle), 0.18 + 0.06 * ((index * 7) % 4), radius * math.sin(angle)), (0.07, 0.055, 0.065), (0.94, 0.68, 0.74) if index % 2 else (0.97, 0.91, 0.82), 8, 5)
        mesh.box((0, 0.005, 0), (w, 0.01, d), (0.22, 0.48, 0.25))
    elif spec.recipe == "candles":
        mesh.cylinder((0, 0, 0), (0, h * 0.78, 0), w * 0.33, (0.96, 0.92, 0.82), 12)
        mesh.sphere((0, h * 0.88, 0), (w * 0.18, h * 0.12, d * 0.18), (1.0, 0.72, 0.28), 8, 5)
        mesh.box((0, 0.005, 0), (w, 0.01, d), (0.70, 0.65, 0.58))
    elif spec.recipe == "mehndi_stage":
        yellow, pink, green, orange, gold = (0.96, 0.66, 0.08), (0.91, 0.30, 0.55), (0.22, 0.55, 0.28), (0.95, 0.40, 0.10), (0.72, 0.52, 0.16)
        mesh.box((0, 0.10, 0), (w, 0.20, d), gold)
        for x, panel_w, panel_h, color in ((-1.55, 1.1, 2.45, yellow), (-0.55, 1.15, 2.75, pink), (0.55, 1.15, 2.75, green), (1.55, 1.1, 2.45, orange)):
            mesh.box((x, 0.20 + panel_h / 2, -d / 2 + 0.12), (panel_w, panel_h, 0.18), color)
        mesh.box((0, h - 0.08, -d / 2 + 0.20), (w, 0.16, 0.40), gold)
        mesh.box((0, 0.43, 0.25), (2.2, 0.65, 0.82), (0.88, 0.36, 0.42))
        mesh.box((0, 0.78, 0.52), (1.95, 0.55, 0.28), (0.96, 0.72, 0.22))
        for x in (-2, -1, 0, 1, 2):
            for index in range(7):
                mesh.sphere((x, 0.55 + index * 0.35, -d / 2 + 0.02), (0.07, 0.07, 0.05), yellow if index % 2 else orange, 8, 5)
    elif spec.recipe == "marigold":
        brass, yellow, orange, green = (0.70, 0.48, 0.14), (1.0, 0.68, 0.04), (0.96, 0.36, 0.06), (0.20, 0.46, 0.21)
        mesh.sphere((0, 0.12, 0), (0.24, 0.12, 0.24), brass)
        mesh.cylinder((0, 0.18, 0), (0, h * 0.72, 0), 0.025, green, 8)
        for index in range(18):
            angle = 2 * math.pi * index / 18
            radius = 0.18 if index < 12 else 0.10
            mesh.sphere((radius * math.cos(angle), h * 0.72 + 0.17 * math.sin(angle * 3) + (0.12 if index >= 12 else 0), radius * math.sin(angle)), (0.075, 0.065, 0.07), yellow if index % 3 else orange, 8, 5)
        mesh.box((0, 0.01, 0), (w, 0.02, d), brass)
    elif spec.recipe == "mehndi_table":
        brass, wood, textile = (0.72, 0.50, 0.16), (0.42, 0.24, 0.10), (0.94, 0.36, 0.24)
        mesh.box((0, 0.08, 0), (w, 0.16, d), wood)
        mesh.box((0, 0.175, 0), (w * 0.94, 0.03, d * 0.94), textile)
        mesh.cylinder((0, 0.20, 0), (0, 0.30, 0), w * 0.23, brass, 16)
        mesh.sphere((0, 0.32, 0), (w * 0.25, 0.03, d * 0.25), brass, 12, 4)
    elif spec.recipe == "festoon":
        cable, warm = (0.18, 0.16, 0.14), (1.0, 0.72, 0.25)
        mesh.cylinder((-w / 2, h / 2, 0), (w / 2, h / 2, 0), 0.006, cable, 6)
        for index in range(17):
            x = -w / 2 + w * index / 16
            mesh.cylinder((x, h / 2, 0), (x, h * 0.20, 0), 0.003, cable, 6)
            mesh.sphere((x, h * 0.15, 0), (0.025, 0.03, 0.025), warm, 8, 5)
        mesh.box((0, h / 2, 0), (w, 0.002, d), cable)
    else:
        raise ValueError(f"Unknown recipe {spec.recipe}")
    mesh.fit_bounds(w, d, h)
    return mesh


def _pack_vec3(values):
    flat = [component for value in values for component in value]
    return struct.pack("<" + "f" * len(flat), *flat)


def _build_glb(spec: AssetSpec, mesh: Mesh) -> bytes:
    buffer = bytearray()
    views = []

    def add_buffer_view(payload: bytes, target: int) -> int:
        while len(buffer) % 4:
            buffer.append(0)
        offset = len(buffer)
        buffer.extend(payload)
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(payload), "target": target})
        return len(views) - 1

    position_view = add_buffer_view(_pack_vec3(mesh.positions), 34962)
    normal_view = add_buffer_view(_pack_vec3(mesh.normals), 34962)
    color_view = add_buffer_view(_pack_vec3(mesh.colors), 34962)
    index_view = add_buffer_view(struct.pack("<" + "H" * len(mesh.indices), *mesh.indices), 34963)
    minimum = [min(value[index] for value in mesh.positions) for index in range(3)]
    maximum = [max(value[index] for value in mesh.positions) for index in range(3)]

    document = {
        "asset": {"version": "2.0", "generator": "BakeSmart local vertical-slice generator"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{
            "name": "BS_ROOT",
            "mesh": 0,
            "extras": {
                "bakesmart_asset_id": spec.asset_id,
                "bakesmart_catalog_id": spec.catalog_id,
                "bakesmart_units": "metres",
                "bakesmart_dimensions_m": [spec.width_m, spec.depth_m, spec.height_m],
                "bakesmart_anchor_type": spec.anchor_type,
                "bakesmart_manifest_version": "production-assets-v1",
                "bakesmart_vertical_slice": "v1",
            },
        }],
        "meshes": [{
            "name": spec.asset_id,
            "primitives": [{
                "attributes": {"POSITION": 0, "NORMAL": 1, "COLOR_0": 2},
                "indices": 3,
                "material": 0,
                "mode": 4,
            }],
        }],
        "materials": [{
            "name": "BakeSmartPrototypePBR",
            "pbrMetallicRoughness": {
                "baseColorFactor": list(spec.base_color),
                "metallicFactor": spec.metallic,
                "roughnessFactor": spec.roughness,
            },
            "doubleSided": True,
        }],
        "buffers": [{"byteLength": len(buffer)}],
        "bufferViews": views,
        "accessors": [
            {"bufferView": position_view, "componentType": 5126, "count": len(mesh.positions), "type": "VEC3", "min": minimum, "max": maximum},
            {"bufferView": normal_view, "componentType": 5126, "count": len(mesh.normals), "type": "VEC3"},
            {"bufferView": color_view, "componentType": 5126, "count": len(mesh.colors), "type": "VEC3"},
            {"bufferView": index_view, "componentType": 5123, "count": len(mesh.indices), "type": "SCALAR", "min": [min(mesh.indices)], "max": [max(mesh.indices)]},
        ],
    }

    json_chunk = json.dumps(document, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    binary_chunk = bytes(buffer)
    while len(binary_chunk) % 4:
        binary_chunk += b"\x00"
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    return (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(binary_chunk), 0x004E4942)
        + binary_chunk
    )


SPEC_BY_ASSET_ID = {spec.asset_id: spec for spec in SPECS}
REVIEW_ASSET_IDS = tuple(spec.asset_id for spec in SPECS)


def build_review_asset_bytes(asset_id: str) -> bytes:
    """Build one deterministic review GLB using only local code and true dimensions."""

    try:
        spec = SPEC_BY_ASSET_ID[asset_id]
    except KeyError as exc:
        raise KeyError(asset_id) from exc
    mesh = _recipe(spec)
    if len(mesh.positions) >= 65535:
        raise ValueError(
            f"{spec.asset_id} exceeds the uint16 review-viewer vertex limit"
        )
    return _build_glb(spec, mesh)


def generate_review_asset_map() -> dict[str, bytes]:
    """Generate all twelve vertical-slice review GLBs in memory."""

    return {
        asset_id: build_review_asset_bytes(asset_id)
        for asset_id in REVIEW_ASSET_IDS
    }
