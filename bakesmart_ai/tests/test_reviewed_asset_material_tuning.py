from pathlib import Path

from tools.tune_reviewed_asset_materials import _decode


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = PACKAGE_ROOT / "app" / "assets" / "production"


def _materials(filename: str) -> dict[str, dict]:
    document, _ = _decode((PRODUCTION / filename).read_bytes())
    return {material["name"]: material for material in document["materials"]}


def test_marigold_review_correction_keeps_dark_materials_visible() -> None:
    materials = _materials("floor-marigold-clusters.glb")
    leaf = materials["BS_PolishLeaf"]["pbrMetallicRoughness"]
    stem = materials["BS_PolishStem"]["pbrMetallicRoughness"]
    brass = materials["BS_BrassPot"]["pbrMetallicRoughness"]

    assert leaf["baseColorFactor"][1] >= 0.30
    assert stem["baseColorFactor"][1] >= 0.15
    assert brass["baseColorFactor"][:3] == [0.95, 0.58, 0.16]
    assert brass["metallicFactor"] <= 0.20


def test_mirror_review_correction_does_not_depend_on_environment_reflections() -> None:
    materials = _materials("sign-mirror-welcome.glb")
    mirror = materials["BS_MirrorSilver"]
    frame = materials["BS_MirrorFrameGold"]["pbrMetallicRoughness"]
    lettering = materials["BS_WelcomeLettering"]

    assert mirror["pbrMetallicRoughness"]["metallicFactor"] <= 0.20
    assert mirror["emissiveFactor"] == [0.12, 0.15, 0.17]
    assert frame["metallicFactor"] <= 0.25
    assert lettering["emissiveFactor"][0] >= 0.18
