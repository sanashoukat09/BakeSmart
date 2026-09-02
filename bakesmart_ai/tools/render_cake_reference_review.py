"""Render deterministic diagnostic PNGs from packaged cake reference GLBs."""

from __future__ import annotations

import argparse
import io
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "cake_references_v1" / "manifest.json"
ASSET_ROOT = ROOT / "app" / "assets" / "cake_references"
OUTPUT_ROOT = ROOT / "data" / "cake_references_v1" / "review_renders"

COMPONENT_DTYPES = {
    5121: np.dtype("u1"),
    5123: np.dtype("<u2"),
    5125: np.dtype("<u4"),
    5126: np.dtype("<f4"),
}
COMPONENT_COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _parse_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise ValueError(f"invalid GLB header: {path}")
    offset = 12
    document = None
    binary = None
    while offset + 8 <= len(data):
        length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + length]
        if chunk_type == 0x4E4F534A:
            document = json.loads(payload.rstrip(b" \t\r\n\0").decode("utf-8"))
        elif chunk_type == 0x004E4942:
            binary = payload
        offset += 8 + length
    if document is None or binary is None:
        raise ValueError(f"GLB is missing JSON or binary data: {path}")
    return document, binary


def _accessor(document: dict, binary: bytes, index: int) -> np.ndarray:
    accessor = document["accessors"][index]
    view = document["bufferViews"][accessor["bufferView"]]
    dtype = COMPONENT_DTYPES[accessor["componentType"]]
    components = COMPONENT_COUNTS[accessor["type"]]
    count = int(accessor["count"])
    offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    packed_width = dtype.itemsize * components
    stride = int(view.get("byteStride", packed_width))
    values = np.ndarray(
        shape=(count, components),
        dtype=dtype,
        buffer=binary,
        offset=offset,
        strides=(stride, dtype.itemsize),
    )
    return np.array(values, copy=True)


def _base_color_image(document: dict, binary: bytes, material_index: int) -> Image.Image:
    material = document["materials"][material_index]
    texture_index = material["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    image_index = document["textures"][texture_index]["source"]
    image_record = document["images"][image_index]
    view = document["bufferViews"][image_record["bufferView"]]
    start = int(view.get("byteOffset", 0))
    end = start + int(view["byteLength"])
    return Image.open(io.BytesIO(binary[start:end])).convert("RGB")


def render(path: Path, output: Path, title: str) -> dict[str, int]:
    document, binary = _parse_glb(path)
    primitive = document["meshes"][0]["primitives"][0]
    positions = _accessor(document, binary, primitive["attributes"]["POSITION"]).astype(float)
    normals = _accessor(document, binary, primitive["attributes"]["NORMAL"]).astype(float)
    indices = _accessor(document, binary, primitive["indices"]).reshape(-1).astype(np.int64)
    triangles = indices.reshape(-1, 3)
    has_texture = "TEXCOORD_0" in primitive["attributes"]
    if has_texture:
        uvs = _accessor(document, binary, primitive["attributes"]["TEXCOORD_0"]).astype(float)
        texture = np.asarray(_base_color_image(document, binary, primitive["material"]))
        texture_height, texture_width = texture.shape[:2]
        vertex_colors = None
    else:
        uvs = None
        texture = None
        texture_height = texture_width = 0
        color_index = primitive["attributes"].get("COLOR_0")
        vertex_colors = (
            _accessor(document, binary, color_index).astype(float)
            if color_index is not None
            else np.ones((len(positions), 3), dtype=float)
        )

    center = (positions.min(axis=0) + positions.max(axis=0)) / 2
    centered = positions - center
    yaw = math.radians(-32)
    pitch = math.radians(18)
    rotation_y = np.array(
        [[math.cos(yaw), 0, math.sin(yaw)], [0, 1, 0], [-math.sin(yaw), 0, math.cos(yaw)]]
    )
    rotation_x = np.array(
        [[1, 0, 0], [0, math.cos(pitch), -math.sin(pitch)], [0, math.sin(pitch), math.cos(pitch)]]
    )
    rotation = rotation_x @ rotation_y
    transformed = centered @ rotation.T
    transformed_normals = normals @ rotation.T

    width, height = 900, 700
    margin_x, margin_y = 120, 105
    span_x = max(float(np.ptp(transformed[:, 0])), 1e-6)
    span_y = max(float(np.ptp(transformed[:, 1])), 1e-6)
    scale = min((width - margin_x * 2) / span_x, (height - margin_y * 2) / span_y)
    screen = np.empty((len(transformed), 2), dtype=float)
    screen[:, 0] = width / 2 + transformed[:, 0] * scale
    screen[:, 1] = height / 2 - transformed[:, 1] * scale + 24

    canvas = Image.new("RGB", (width, height), (239, 232, 226))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.ellipse((205, 565, 695, 640), fill=(60, 42, 36, 32))
    draw.rounded_rectangle((18, 16, 882, 66), radius=14, fill=(255, 255, 255, 224))
    draw.text((36, 31), f"{title} • packaged GLB diagnostic render", fill=(55, 32, 42, 255))

    light = np.array([0.42, 0.78, 0.46], dtype=float)
    light /= np.linalg.norm(light)
    order = np.argsort(transformed[triangles, 2].mean(axis=1))
    for triangle_index in order:
        vertex_ids = triangles[triangle_index]
        points = [tuple(screen[index]) for index in vertex_ids]
        normal = transformed_normals[vertex_ids].mean(axis=0)
        length = np.linalg.norm(normal)
        if length:
            normal /= length
        brightness = 0.38 + 0.72 * max(float(np.dot(normal, light)), 0.0)
        if has_texture:
            uv = uvs[vertex_ids].mean(axis=0)
            x = int((uv[0] % 1.0) * (texture_width - 1))
            y = int((1.0 - (uv[1] % 1.0)) * (texture_height - 1))
            base = texture[y, x].astype(float)
        else:
            base = np.clip(vertex_colors[vertex_ids, :3].mean(axis=0) * 255, 0, 255)
        color = tuple(int(np.clip(channel * brightness, 0, 255)) for channel in base)
        draw.polygon(points, fill=(*color, 255))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)
    return {
        "triangles": len(triangles),
        "vertices": len(positions),
        "texture_width": texture_width,
        "texture_height": texture_height,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for asset in manifest["assets"]:
        source_id = asset["source_id"]
        metrics = render(
            ASSET_ROOT / asset["file_name"],
            args.output / f"{source_id}.png",
            source_id.replace("ph-", "").replace("-", " ").title(),
        )
        print(f"Rendered {source_id}: {json.dumps(metrics, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
