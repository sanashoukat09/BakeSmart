from __future__ import annotations

import json
import struct

from app.services.cake_reference_assets import cake_reference_asset_store
from app.services.cake_references import cake_reference_library


def _glb_document(data: bytes) -> dict:
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(data)
    json_length, json_type = struct.unpack_from("<II", data, 12)
    assert json_type == 0x4E4F534A
    return json.loads(data[20 : 20 + json_length].decode("utf-8"))


def test_packaged_reference_cakes_are_self_contained_and_review_only():
    response = cake_reference_asset_store.response()

    assert response["reference_only"] is True
    assert response["production_ready"] is False
    assert {asset["source_id"] for asset in response["assets"]} == {
        "ph-carrot-cake",
        "ph-strawberry-chocolate-cake",
    }
    for asset in response["assets"]:
        path = cake_reference_asset_store.glb_path(asset["source_id"])
        document = _glb_document(path.read_bytes())
        extras = document["asset"]["extras"]
        assert document["buffers"] == [{"byteLength": document["buffers"][0]["byteLength"]}]
        assert all("uri" not in image and "bufferView" in image for image in document["images"])
        assert extras["bakesmart_source_id"] == asset["source_id"]
        assert extras["bakesmart_license"] == "CC0-1.0"
        assert extras["bakesmart_units"] == "metres"
        assert extras["bakesmart_reference_only"] is True
        assert extras["bakesmart_production_ready"] is False
        assert extras["bakesmart_configurable"] is False


def test_reference_profile_selection_is_deterministic_and_style_aware():
    rustic = cake_reference_library.select("rustic-boho-cake-01")
    chocolate = cake_reference_library.select("dark-moody-chocolate-cake")
    classic = cake_reference_library.select("classic-elegant-cake-01")
    unknown = cake_reference_library.select(None)

    assert rustic.source_id == "ph-strawberry-chocolate-cake"
    assert chocolate.source_id == "ph-carrot-cake"
    assert classic.source_id == "bakesmart-authored-neutral"
    assert unknown == cake_reference_library.default


def test_configurable_profiles_use_readable_piping_and_toppers():
    """Prevent the tiny decoration regression found during visual QA."""
    for profile in cake_reference_library.profiles:
        assert profile.piping_radius_fraction >= 0.019
        assert profile.topper_cluster_radius_fraction >= 0.11
