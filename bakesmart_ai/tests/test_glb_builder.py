from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from app.schemas.design import DesignRequest
from app.services.catalog import CatalogStore
from app.services.feature_adapter import RequestFeatureAdapter
from app.services.glb_builder import (
    BIN_CHUNK_TYPE,
    GLB_MAGIC,
    GLB_VERSION,
    JSON_CHUNK_TYPE,
    ProceduralGlbBuilder,
)
from app.services.scene_artifacts import SceneArtifactStore
from app.services.scene_builder import SceneBuilder
from training.model_runtime import BootstrapModelRuntime


def _parse_glb(data: bytes) -> tuple[dict, bytes]:
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    assert magic == GLB_MAGIC
    assert version == GLB_VERSION
    assert total_length == len(data)

    json_length, json_type = struct.unpack_from("<II", data, 12)
    assert json_type == JSON_CHUNK_TYPE
    json_start = 20
    document = json.loads(
        data[json_start : json_start + json_length].decode("utf-8")
    )
    binary_header = json_start + json_length
    binary_length, binary_type = struct.unpack_from("<II", data, binary_header)
    assert binary_type == BIN_CHUNK_TYPE
    binary_start = binary_header + 8
    binary = data[binary_start : binary_start + binary_length]
    assert binary_start + binary_length == len(data)
    return document, binary


def _generated_scene(valid_design_request: dict):
    request = DesignRequest.model_validate(valid_design_request)
    runtime = BootstrapModelRuntime.load()
    features = RequestFeatureAdapter.load().transform(request)
    signals = runtime.predict(features.matrix)[0]
    catalog = CatalogStore()
    scene_result = SceneBuilder(catalog).build(request, signals)
    palette = catalog.themes[scene_result.selected_theme_id]["palette_hex"]
    generated = ProceduralGlbBuilder().build(
        request,
        scene_result.scene,
        scene_result.cake,
        palette,
        "design-1234567890abcdef1234",
    )
    return generated


def test_procedural_glb_is_deterministic_and_structurally_valid(
    valid_design_request,
):
    first = _generated_scene(valid_design_request)
    second = _generated_scene(valid_design_request)

    assert first.data == second.data
    assert first.vertex_count > 100
    assert first.triangle_count > 100
    assert all(
        minimum < maximum
        for minimum, maximum in zip(
            first.bounds_min, first.bounds_max, strict=True
        )
    )

    document, binary = _parse_glb(first.data)
    assert document["asset"]["version"] == "2.0"
    assert document["asset"]["generator"] == (
        "BakeSmart procedural GLB exporter"
    )
    assert document["asset"]["extras"]["procedural_concept"] is True
    assert document["scene"] == 0
    primitive = document["meshes"][0]["primitives"][0]
    assert primitive["attributes"] == {
        "COLOR_0": 2,
        "NORMAL": 1,
        "POSITION": 0,
    }
    assert primitive["mode"] == 4
    assert document["accessors"][0]["count"] == first.vertex_count
    assert document["accessors"][3]["count"] == first.triangle_count * 3
    assert document["buffers"][0]["byteLength"] <= len(binary)
    assert all(
        buffer_view["byteOffset"] % 4 == 0
        for buffer_view in document["bufferViews"]
    )
    assert document["accessors"][3]["max"][0] < first.vertex_count


def test_scene_artifact_store_rejects_path_traversal(tmp_path: Path):
    store = SceneArtifactStore(tmp_path / "scenes")
    design_id = "design-1234567890abcdef1234"
    generated_data = b"glTF" + b"\x00" * 32

    path = store.write(design_id, generated_data)

    assert path == tmp_path / "scenes" / f"{design_id}.glb"
    assert store.existing_path(design_id) == path
    assert path.read_bytes() == generated_data
    with pytest.raises(ValueError, match="invalid"):
        store.path_for("../../main")
    with pytest.raises(ValueError, match="GLB"):
        store.write(design_id, b"not a scene")
