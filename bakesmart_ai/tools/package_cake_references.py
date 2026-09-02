"""Package verified Poly Haven cake glTF sources into review-only GLBs."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import struct
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "assets" / "third_party_cc0" / "raw"
RECEIPT_ROOT = ROOT / "data" / "professional_asset_sources_v1" / "download_receipts"
OUTPUT_ROOT = ROOT / "app" / "assets" / "cake_references"
MANIFEST_PATH = ROOT / "data" / "cake_references_v1" / "manifest.json"

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK_TYPE = 0x4E4F534A
BIN_CHUNK_TYPE = 0x004E4942

CAKE_SOURCES = {
    "ph-carrot-cake": "carrot_cake_1k.gltf",
    "ph-strawberry-chocolate-cake": "strawberry_chocolate_cake_1k.gltf",
}


def _safe_relative_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe source-relative path: {value!r}")
    return Path(*path.parts)


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_receipt(source_id: str, source_dir: Path) -> dict[str, Any]:
    receipt_path = RECEIPT_ROOT / f"{source_id}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("source_id") != source_id:
        raise ValueError(f"receipt source id does not match {source_id}")
    if not (
        receipt.get("license") == "CC0-1.0"
        and receipt.get("license_verified") is True
        and receipt.get("redistribution_allowed") is True
        and receipt.get("ai_generated") is False
    ):
        raise ValueError(f"receipt rights gate failed for {source_id}")
    for record in receipt.get("files", []):
        path = source_dir / _safe_relative_path(str(record["relative_path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size != int(record["size_bytes"]):
            raise ValueError(f"receipt size mismatch for {path}")
        if _md5(path).lower() != str(record["md5"]).lower():
            raise ValueError(f"receipt checksum mismatch for {path}")
    return receipt


def _append_aligned(binary: bytearray, payload: bytes) -> tuple[int, int]:
    while len(binary) % 4:
        binary.append(0)
    offset = len(binary)
    binary.extend(payload)
    return offset, len(payload)


def _mesh_metrics(document: dict[str, Any]) -> tuple[list[float], int, int]:
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    triangles = 0
    vertices = 0
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            position_index = primitive.get("attributes", {}).get("POSITION")
            if position_index is None:
                continue
            position = document["accessors"][position_index]
            vertices += int(position.get("count", 0))
            for axis in range(3):
                minimum[axis] = min(minimum[axis], float(position["min"][axis]))
                maximum[axis] = max(maximum[axis], float(position["max"][axis]))
            index = primitive.get("indices")
            if index is not None and int(primitive.get("mode", 4)) == 4:
                triangles += int(document["accessors"][index]["count"]) // 3
    if any(value in {float("inf"), float("-inf")} for value in minimum + maximum):
        raise ValueError("cake source has no measurable POSITION bounds")
    dimensions = [maximum[0] - minimum[0], maximum[2] - minimum[2], maximum[1] - minimum[1]]
    return dimensions, vertices, triangles


def package_gltf(
    gltf_path: Path,
    *,
    source_id: str,
    receipt: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    source_dir = gltf_path.parent
    document = json.loads(gltf_path.read_text(encoding="utf-8"))
    buffers = document.get("buffers", [])
    if len(buffers) != 1 or not isinstance(buffers[0].get("uri"), str):
        raise ValueError("cake packager requires exactly one external source buffer")
    buffer_path = source_dir / _safe_relative_path(buffers[0]["uri"])
    binary = bytearray(buffer_path.read_bytes())
    if len(binary) != int(buffers[0]["byteLength"]):
        raise ValueError("source buffer length does not match glTF declaration")

    buffer_views = document.setdefault("bufferViews", [])
    for image in document.get("images", []):
        uri = image.get("uri")
        if not isinstance(uri, str):
            raise ValueError("cake packager requires external source images")
        image_path = source_dir / _safe_relative_path(uri)
        payload = image_path.read_bytes()
        offset, length = _append_aligned(binary, payload)
        buffer_view = len(buffer_views)
        buffer_views.append(
            {"buffer": 0, "byteOffset": offset, "byteLength": length}
        )
        image.pop("uri", None)
        image["bufferView"] = buffer_view
        image["mimeType"] = image.get("mimeType") or mimetypes.guess_type(image_path)[0]
        if image["mimeType"] not in {"image/jpeg", "image/png"}:
            raise ValueError(f"unsupported cake texture type: {image['mimeType']}")

    dimensions, vertices, triangles = _mesh_metrics(document)
    asset = document.setdefault("asset", {"version": "2.0"})
    if str(asset.get("version")) != "2.0":
        raise ValueError("only glTF 2.0 cake sources are supported")
    existing_extras = asset.get("extras") if isinstance(asset.get("extras"), dict) else {}
    asset["extras"] = {
        **existing_extras,
        "bakesmart_source_id": source_id,
        "bakesmart_source_page": receipt["source_page"],
        "bakesmart_license": receipt["license"],
        "bakesmart_units": "metres",
        "bakesmart_dimensions_m": [round(value, 6) for value in dimensions],
        "bakesmart_anchor_type": "surface_center",
        "bakesmart_reference_only": True,
        "bakesmart_production_ready": False,
        "bakesmart_configurable": False,
    }
    buffers[0] = {"byteLength": len(binary)}

    json_bytes = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
    json_bytes += b" " * ((-len(json_bytes)) % 4)
    binary_byte_length = len(binary)
    while len(binary) % 4:
        binary.append(0)
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)
    output = bytearray(struct.pack("<4sII", GLB_MAGIC, GLB_VERSION, total_length))
    output.extend(struct.pack("<II", len(json_bytes), JSON_CHUNK_TYPE))
    output.extend(json_bytes)
    output.extend(struct.pack("<II", len(binary), BIN_CHUNK_TYPE))
    output.extend(binary)

    result = bytes(output)
    metrics = {
        "source_id": source_id,
        "file_name": f"{source_id}.glb",
        "source_page": receipt["source_page"],
        "license": receipt["license"],
        "dimensions_m": {
            "width": round(dimensions[0], 6),
            "depth": round(dimensions[1], 6),
            "height": round(dimensions[2], 6),
        },
        "vertex_count": vertices,
        "triangle_count": triangles,
        "texture_count": len(document.get("images", [])),
        "file_size_bytes": len(result),
        "sha256": hashlib.sha256(result).hexdigest(),
        "status": "reference_review",
        "production_ready": False,
        "configurable": False,
    }
    if binary_byte_length != document["buffers"][0]["byteLength"]:
        raise AssertionError("GLB binary metadata changed during packaging")
    return result, metrics


def build_all(output_root: Path = OUTPUT_ROOT, manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for source_id, file_name in CAKE_SOURCES.items():
        source_dir = RAW_ROOT / source_id
        receipt = _verified_receipt(source_id, source_dir)
        data, metrics = package_gltf(
            source_dir / file_name,
            source_id=source_id,
            receipt=receipt,
        )
        output_path = output_root / metrics["file_name"]
        output_path.write_bytes(data)
        records.append(metrics)
        print(
            f"Packaged {source_id}: {metrics['triangle_count']} triangles, "
            f"{metrics['file_size_bytes']} bytes -> {output_path}"
        )
    manifest = {
        "schema_version": 1,
        "library_id": "cake-references-v1",
        "reference_only": True,
        "production_ready": False,
        "assets": records,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()
    build_all(args.output, args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
