import hashlib
from pathlib import Path

from tools.collect_professional_assets import _download, _polyhaven_pbr_plan


def _record(name: str, payload: bytes = b"map") -> dict[str, object]:
    return {
        "url": f"https://example.test/{name}.jpg",
        "size": len(payload),
        "md5": hashlib.md5(payload).hexdigest(),
    }


def test_pbr_plan_requires_complete_webgl_material_set():
    files = {
        "Diffuse": {"1k": {"jpg": _record("fabric_diff_1k")}},
        "nor_gl": {"1k": {"jpg": _record("fabric_nor_gl_1k")}},
    }

    try:
        _polyhaven_pbr_plan(files, "fabric")
    except RuntimeError as exc:
        assert "packed ARM" in str(exc)
    else:
        raise AssertionError("An incomplete PBR set was accepted")


def test_pbr_plan_includes_required_and_available_anisotropy_maps():
    files = {
        "Diffuse": {"1k": {"jpg": _record("fabric_diff_1k")}},
        "nor_gl": {"1k": {"jpg": _record("fabric_nor_gl_1k")}},
        "arm": {"1k": {"jpg": _record("fabric_arm_1k")}},
        "anisotropy_strength": {
            "1k": {"jpg": _record("fabric_anisotropy_strength_1k")}
        },
        "anisotropy_rotation": {
            "1k": {"jpg": _record("fabric_anisotropy_rotation_1k")}
        },
    }

    plan = _polyhaven_pbr_plan(files, "fabric")

    assert [path.name for path, *_rest in plan] == [
        "fabric_diff_1k.jpg",
        "fabric_nor_gl_1k.jpg",
        "fabric_arm_1k.jpg",
        "fabric_anisotropy_strength_1k.jpg",
        "fabric_anisotropy_rotation_1k.jpg",
    ]


def test_download_reuses_only_checksum_verified_existing_file(tmp_path: Path):
    payload = b"already downloaded"
    destination = tmp_path / "asset.bin"
    destination.write_bytes(payload)
    expected = hashlib.md5(payload).hexdigest()

    size, digest, newly_downloaded = _download(
        "https://example.test/asset.bin",
        destination,
        expected,
    )

    assert size == len(payload)
    assert digest == expected
    assert newly_downloaded is False
