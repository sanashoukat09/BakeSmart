"""Apply checksum-gated material corrections from production visual review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import tempfile
from pathlib import Path
from typing import Any


GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
REVIEWED_SHA256 = {
    "floor-marigold-clusters.glb": "55fd69bb7d7d6386cb597fe8bd18048c2c96cf76de9819b8422e4c78c17f0178",
    "sign-mirror-welcome.glb": "dda7a5f7951e52f944a7f2cce52812cb5885debfc6f0438422b3df71c8db47ee",
}
MATERIALS = {
    "floor-marigold-clusters.glb": {
        "BS_PolishLeaf": ([0.07, 0.30, 0.035, 1.0], 0.0, 0.72, [0.006, 0.018, 0.003]),
        "BS_PolishStem": ([0.035, 0.15, 0.018, 1.0], 0.0, 0.78, [0.003, 0.010, 0.002]),
        "BS_BrassPot": ([0.95, 0.58, 0.16, 1.0], 0.18, 0.38, [0.035, 0.016, 0.003]),
    },
    "sign-mirror-welcome.glb": {
        "BS_Stand": ([0.90, 0.62, 0.20, 1.0], 0.22, 0.34, [0.025, 0.012, 0.002]),
        "BS_MirrorSilver": ([0.72, 0.82, 0.88, 1.0], 0.16, 0.22, [0.12, 0.15, 0.17]),
        "BS_WelcomeLettering": ([1.0, 0.80, 0.26, 1.0], 0.05, 0.28, [0.18, 0.10, 0.012]),
        "BS_MirrorFrameGold": ([0.92, 0.64, 0.22, 1.0], 0.24, 0.32, [0.030, 0.015, 0.003]),
    },
}


def _decode(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) < 20:
        raise ValueError("GLB is too small.")
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC or version != GLB_VERSION or declared_length != len(data):
        raise ValueError("Invalid GLB header.")
    document: dict[str, Any] | None = None
    binary = b""
    offset = 12
    while offset < len(data):
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        payload = data[offset : offset + length]
        offset += length
        if chunk_type == JSON_CHUNK:
            document = json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif chunk_type == BIN_CHUNK:
            binary = payload
    if not isinstance(document, dict):
        raise ValueError("GLB JSON document is missing.")
    return document, binary


def _encode(document: dict[str, Any], binary: bytes) -> bytes:
    encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded += b" " * ((4 - len(encoded) % 4) % 4)
    chunks = struct.pack("<II", len(encoded), JSON_CHUNK) + encoded
    if binary:
        binary += b"\x00" * ((4 - len(binary) % 4) % 4)
        chunks += struct.pack("<II", len(binary), BIN_CHUNK) + binary
    return struct.pack("<4sII", GLB_MAGIC, GLB_VERSION, 12 + len(chunks)) + chunks


def tune(path: Path) -> str:
    expected = REVIEWED_SHA256.get(path.name)
    if expected is None:
        raise ValueError(f"Unsupported reviewed asset: {path.name}")
    source = path.read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    if actual != expected:
        raise ValueError(f"Checksum mismatch for {path.name}: {actual}")
    document, binary = _decode(source)
    by_name = {material.get("name"): material for material in document.get("materials", [])}
    for name, (color, metallic, roughness, emissive) in MATERIALS[path.name].items():
        material = by_name.get(name)
        if material is None:
            raise ValueError(f"Required material is missing: {name}")
        pbr = material.setdefault("pbrMetallicRoughness", {})
        pbr["baseColorFactor"] = color
        pbr["metallicFactor"] = metallic
        pbr["roughnessFactor"] = roughness
        material["emissiveFactor"] = emissive
    payload = _encode(document, binary)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        print(f"{path.name}: {tune(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
