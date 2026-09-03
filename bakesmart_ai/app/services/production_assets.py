"""Local production-asset manifest, GLB validation, and readiness checks."""

from __future__ import annotations

import csv
import json
import struct
from math import sqrt
from pathlib import Path
from typing import Any

from app.schemas.assets import (
    AssetBoundsCoverage,
    MaterialProfileRecord,
    ProductionAssetCatalogResponse,
    ProductionAssetLibrarySummary,
    ProductionAssetRecord,
    ProductionAssetValidationResponse,
)
from app.schemas.design import Dimensions
from app.services.real_decor_catalog import RealDecorCatalog


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_DATA_DIR = PACKAGE_ROOT / "data" / "production_assets_v1"
MAX_MODULE_FILE_BYTES = 25 * 1024 * 1024
MIN_VISIBLE_AXIS_COVERAGE = 0.85
MAX_VISIBLE_ENVELOPE_OVERFLOW_M = 0.02
GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK_TYPE = 0x4E4F534A


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"expected boolean text, got '{value}'")
    return normalized == "true"


def _round_dimensions(values: list[float]) -> tuple[float, float, float]:
    return tuple(round(float(value), 4) for value in values)


def _find_pipeline_extras(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        extras = value.get("extras")
        if isinstance(extras, dict) and "bakesmart_asset_id" in extras:
            return extras
        for nested in value.values():
            found = _find_pipeline_extras(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_pipeline_extras(nested)
            if found is not None:
                return found
    return None


def _triangle_count(document: dict[str, Any]) -> int:
    accessors = document.get("accessors", [])
    total = 0
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            mode = primitive.get("mode", 4)
            if mode != 4:
                continue
            accessor_index = primitive.get("indices")
            if isinstance(accessor_index, int) and 0 <= accessor_index < len(accessors):
                total += int(accessors[accessor_index].get("count", 0)) // 3
                continue
            position_index = primitive.get("attributes", {}).get("POSITION")
            if isinstance(position_index, int) and 0 <= position_index < len(accessors):
                total += int(accessors[position_index].get("count", 0)) // 3
    return total


def _glb_json_document(data: bytes) -> dict[str, Any] | None:
    """Decode the first GLB JSON chunk after lightweight header validation."""

    if len(data) < 20:
        return None
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC or version != GLB_VERSION or declared_length != len(data):
        return None
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != JSON_CHUNK_TYPE or 20 + chunk_length > len(data):
        return None
    try:
        decoded = json.loads(
            data[20 : 20 + chunk_length]
            .rstrip(b" \t\r\n\x00")
            .decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _identity_matrix() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _multiply_matrices(
    left: list[list[float]],
    right: list[list[float]],
) -> list[list[float]]:
    return [
        [
            sum(left[row][inner] * right[inner][column] for inner in range(4))
            for column in range(4)
        ]
        for row in range(4)
    ]


def _node_matrix(node: dict[str, Any]) -> list[list[float]]:
    encoded = node.get("matrix")
    if isinstance(encoded, list) and len(encoded) == 16:
        return [
            [float(encoded[column * 4 + row]) for column in range(4)]
            for row in range(4)
        ]

    translation = node.get("translation", [0.0, 0.0, 0.0])
    scale = node.get("scale", [1.0, 1.0, 1.0])
    rotation = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    if not all(
        isinstance(value, (int, float))
        for value in [*translation, *scale, *rotation]
    ):
        raise ValueError("node transform contains non-numeric values")
    x, y, z, w = (float(value) for value in rotation)
    magnitude = sqrt(x * x + y * y + z * z + w * w)
    if magnitude == 0:
        raise ValueError("node quaternion has zero length")
    x, y, z, w = (value / magnitude for value in (x, y, z, w))
    sx, sy, sz = (float(value) for value in scale)
    tx, ty, tz = (float(value) for value in translation)
    return [
        [(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y - z * w) * sy, 2 * (x * z + y * w) * sz, tx],
        [2 * (x * y + z * w) * sx, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z - x * w) * sz, ty],
        [2 * (x * z - y * w) * sx, 2 * (y * z + x * w) * sy, (1 - 2 * (x * x + y * y)) * sz, tz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _transform_point(
    matrix: list[list[float]],
    point: tuple[float, float, float],
) -> tuple[float, float, float]:
    x, y, z = point
    return tuple(
        matrix[row][0] * x
        + matrix[row][1] * y
        + matrix[row][2] * z
        + matrix[row][3]
        for row in range(3)
    )


def _visible_mesh_dimensions(
    document: dict[str, Any],
) -> tuple[float, float, float] | None:
    """Return world-space width/depth/height from glTF POSITION accessor bounds.

    glTF is Y-up, so its world X/Y/Z extents map to BakeSmart width/height/depth.
    Accessor bounds are checked independently instead of trusting exported extras.
    """

    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    accessors = document.get("accessors", [])
    if not nodes or not meshes or not accessors:
        return None
    scene_index = document.get("scene", 0)
    scenes = document.get("scenes", [])
    if not isinstance(scene_index, int) or not 0 <= scene_index < len(scenes):
        return None
    root_indices = scenes[scene_index].get("nodes", [])
    points: list[tuple[float, float, float]] = []

    def visit(node_index: int, parent_matrix: list[list[float]], active: set[int]) -> None:
        if not isinstance(node_index, int) or not 0 <= node_index < len(nodes):
            raise ValueError("scene references an invalid node index")
        if node_index in active:
            raise ValueError("node hierarchy contains a cycle")
        node = nodes[node_index]
        world = _multiply_matrices(parent_matrix, _node_matrix(node))
        mesh_index = node.get("mesh")
        if isinstance(mesh_index, int) and 0 <= mesh_index < len(meshes):
            for primitive in meshes[mesh_index].get("primitives", []):
                position_index = primitive.get("attributes", {}).get("POSITION")
                if not isinstance(position_index, int) or not 0 <= position_index < len(accessors):
                    continue
                accessor = accessors[position_index]
                minimum = accessor.get("min")
                maximum = accessor.get("max")
                if not (
                    isinstance(minimum, list)
                    and isinstance(maximum, list)
                    and len(minimum) == len(maximum) == 3
                ):
                    continue
                for x in (float(minimum[0]), float(maximum[0])):
                    for y in (float(minimum[1]), float(maximum[1])):
                        for z in (float(minimum[2]), float(maximum[2])):
                            points.append(_transform_point(world, (x, y, z)))
        next_active = {*active, node_index}
        for child_index in node.get("children", []):
            visit(child_index, world, next_active)

    for root_index in root_indices:
        visit(root_index, _identity_matrix(), set())
    if not points:
        return None
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    gltf_extents = [maximum[axis] - minimum[axis] for axis in range(3)]
    return gltf_extents[0], gltf_extents[2], gltf_extents[1]


def _physical_envelopes(record: ProductionAssetRecord) -> tuple[Dimensions, Dimensions]:
    installation = record.dimensions
    padding = record.collision_padding_m
    collision = Dimensions(
        width_m=installation.width_m + 2 * padding,
        depth_m=(installation.depth_m or 0.0) + 2 * padding,
        height_m=installation.height_m,
    )
    return installation, collision


def inspect_glb_bytes(
    data: bytes,
    record: ProductionAssetRecord,
) -> tuple[list[str], list[str], list[str], int | None]:
    """Inspect one GLB without external AI, cloud services, or a rendering engine."""

    checks: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    if len(data) < 20:
        return checks, ["GLB is too small to contain a valid header and JSON chunk."], warnings, None

    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC:
        errors.append("GLB magic header is not 'glTF'.")
    else:
        checks.append("GLB magic header is valid.")
    if version != GLB_VERSION:
        errors.append(f"GLB version must be 2, got {version}.")
    else:
        checks.append("GLB version is 2.")
    if declared_length != len(data):
        errors.append(
            f"GLB declared length {declared_length} does not match file length {len(data)}."
        )
    else:
        checks.append("GLB declared length matches file length.")
    if errors:
        return checks, errors, warnings, None

    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != JSON_CHUNK_TYPE:
        return checks, ["First GLB chunk must be the glTF JSON chunk."], warnings, None
    json_start = 20
    json_end = json_start + chunk_length
    if json_end > len(data):
        return checks, ["GLB JSON chunk exceeds the declared file length."], warnings, None

    try:
        document = json.loads(
            data[json_start:json_end].rstrip(b" \t\r\n\x00").decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return checks, [f"GLB JSON chunk could not be decoded: {exc}"], warnings, None

    if str(document.get("asset", {}).get("version")) != "2.0":
        errors.append("glTF asset.version must be '2.0'.")
    else:
        checks.append("glTF asset.version is 2.0.")

    if not document.get("nodes"):
        errors.append("Production GLB must contain at least one node.")
    else:
        checks.append("At least one node is present.")
    if not document.get("meshes"):
        errors.append("Production GLB must contain at least one mesh.")
    else:
        checks.append("At least one mesh is present.")

    unsupported_required = {
        "KHR_draco_mesh_compression",
        "EXT_meshopt_compression",
    } & set(document.get("extensionsRequired", []))
    if unsupported_required:
        errors.append(
            "Runtime-incompatible required compression extension(s): "
            + ", ".join(sorted(unsupported_required))
        )
    else:
        checks.append("No unsupported required mesh-compression extension is declared.")

    materials = document.get("materials", [])
    if not materials:
        errors.append("Production GLB must contain explicit PBR material definitions.")
    else:
        missing_pbr = [
            index
            for index, material in enumerate(materials)
            if "pbrMetallicRoughness" not in material
        ]
        if missing_pbr:
            errors.append(
                "Every material must define pbrMetallicRoughness; missing on material "
                + ", ".join(map(str, missing_pbr))
                + "."
            )
        else:
            checks.append("All materials define pbrMetallicRoughness.")

    extras = _find_pipeline_extras(document)
    if extras is None:
        errors.append(
            "BakeSmart export metadata is missing; export a BS_ROOT object with custom properties."
        )
    else:
        expected_dimensions = (
            record.dimensions.width_m,
            record.dimensions.depth_m or 0.0,
            record.dimensions.height_m,
        )
        actual_dimensions = extras.get("bakesmart_dimensions_m")
        if extras.get("bakesmart_asset_id") != record.asset_id:
            errors.append("Embedded bakesmart_asset_id does not match the manifest.")
        else:
            checks.append("Embedded asset id matches the manifest.")
        if extras.get("bakesmart_units") != "metres":
            errors.append("Embedded units must be 'metres'.")
        else:
            checks.append("Embedded units are metres.")
        if extras.get("bakesmart_anchor_type") != record.anchor_type:
            errors.append("Embedded anchor type does not match the manifest.")
        else:
            checks.append("Embedded anchor type matches the manifest.")
        if not isinstance(actual_dimensions, (list, tuple)) or len(actual_dimensions) != 3:
            errors.append("Embedded dimensions must be a three-value metre array.")
        else:
            actual = _round_dimensions(list(actual_dimensions))
            expected = _round_dimensions(list(expected_dimensions))
            if any(abs(a - b) > 0.02 for a, b in zip(actual, expected, strict=True)):
                errors.append(
                    f"Embedded dimensions {actual} do not match manifest dimensions {expected} within 2 cm."
                )
            else:
                checks.append("Embedded true-size dimensions match the manifest within 2 cm.")

    try:
        visible_dimensions = _visible_mesh_dimensions(document)
    except (TypeError, ValueError) as exc:
        visible_dimensions = None
        errors.append(f"Visible mesh bounds could not be calculated safely: {exc}.")
    if visible_dimensions is None:
        warnings.append(
            "Visible mesh bounds could not be calculated from POSITION accessor min/max values."
        )
    else:
        expected_dimensions = (
            record.dimensions.width_m,
            record.dimensions.depth_m or 0.0,
            record.dimensions.height_m,
        )
        coverage = tuple(
            measured / expected
            for measured, expected in zip(
                visible_dimensions,
                expected_dimensions,
                strict=True,
            )
        )
        axis_names = ("width", "depth", "height")
        undersized = [
            f"{axis}={fraction:.1%}"
            for axis, fraction in zip(axis_names, coverage, strict=True)
            if fraction < MIN_VISIBLE_AXIS_COVERAGE
        ]
        overflow = [
            f"{axis}={measured:.4f} m vs {expected:.4f} m"
            for axis, measured, expected in zip(
                axis_names,
                visible_dimensions,
                expected_dimensions,
                strict=True,
            )
            if measured > expected + MAX_VISIBLE_ENVELOPE_OVERFLOW_M
        ]
        if undersized:
            errors.append(
                "Visible mesh is too small for its declared installation envelope; "
                "minimum per-axis coverage is 85% (" + ", ".join(undersized) + ")."
            )
        else:
            checks.append(
                "Visible mesh fills at least 85% of the installation envelope on every axis."
            )
        if overflow:
            errors.append(
                "Visible mesh exceeds the installation envelope by more than 2 cm ("
                + ", ".join(overflow)
                + ")."
            )
        else:
            checks.append(
                "Visible mesh stays within the installation envelope plus 2 cm tolerance."
            )

        extras_visible = extras.get("bakesmart_visible_mesh_bounds_m") if extras else None
        if isinstance(extras_visible, (list, tuple)) and len(extras_visible) == 3:
            declared_visible = _round_dimensions(list(extras_visible))
            calculated_visible = _round_dimensions(list(visible_dimensions))
            if any(
                abs(declared - calculated) > 0.02
                for declared, calculated in zip(declared_visible, calculated_visible, strict=True)
            ):
                errors.append(
                    f"Embedded visible mesh bounds {declared_visible} do not match calculated bounds "
                    f"{calculated_visible} within 2 cm."
                )
            else:
                checks.append(
                    "Embedded visible mesh bounds match independently calculated bounds within 2 cm."
                )
        else:
            warnings.append("Embedded bakesmart_visible_mesh_bounds_m metadata is missing.")

    triangles = _triangle_count(document)
    if triangles <= 0:
        warnings.append(
            "Triangle count could not be derived from indexed/position accessors; inspect the asset in Blender."
        )
    elif triangles > record.lod0_triangle_budget:
        errors.append(
            f"LOD0 triangle count {triangles} exceeds the manifest budget "
            f"{record.lod0_triangle_budget}."
        )
    else:
        checks.append(
            f"LOD0 triangle count {triangles} is within the "
            f"{record.lod0_triangle_budget} triangle budget."
        )

    warnings.append(
        "Texture pixel dimensions and visual material quality still require Blender/export review; the binary inspector does not decode every embedded image."
    )
    return checks, errors, warnings, triangles if triangles > 0 else None


class ProductionAssetRegistry:
    """Canonical mapping from real catalogue items to production GLB requirements."""

    _limitations = [
        "The manifest is a production requirement registry; planned rows are not finished 3D assets.",
        "A GLB is renderable only after geometry, PBR, metadata, license, and redistribution checks pass.",
        "The customer viewer assembles approved external modules at true scale and keeps unapproved catalogue items in its procedural fallback GLB.",
        "True-size structural assets are not stretched to fill a large venue; use modular repetition or larger approved modules.",
        "The professional library target is 80-120 production-ready modular GLBs; this v1 manifest first covers every current real catalogue archetype.",
    ]

    def __init__(
        self,
        data_dir: Path = DEFAULT_ASSET_DATA_DIR,
        package_root: Path = PACKAGE_ROOT,
        catalog: RealDecorCatalog | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.package_root = package_root
        self.catalog = catalog or RealDecorCatalog()
        self.material_profiles = self._load_material_profiles()
        self.assets = self._load_assets()
        self.by_asset_id = {asset.asset_id: asset for asset in self.assets}
        self.by_catalog_id = {asset.catalog_id: asset for asset in self.assets}
        self._validation_cache: dict[str, ProductionAssetValidationResponse] = {}
        self._validate_manifest_integrity()

    def _load_material_profiles(self) -> list[MaterialProfileRecord]:
        output: list[MaterialProfileRecord] = []
        for row in _read_csv(self.data_dir / "material_profiles.csv"):
            output.append(
                MaterialProfileRecord(
                    profile_id=row["profile_id"],
                    display_name=row["display_name"],
                    metallic=float(row["metallic"]),
                    roughness=float(row["roughness"]),
                    alpha_mode=row["alpha_mode"],
                    double_sided=_bool(row["double_sided"]),
                    pbr_required=_bool(row["pbr_required"]),
                    base_color_texture_required=_bool(
                        row["base_color_texture_required"]
                    ),
                    orm_texture_required=_bool(row["orm_texture_required"]),
                    emissive_texture_allowed=_bool(row["emissive_texture_allowed"]),
                    texture_max_px=int(row["texture_max_px"]),
                    notes=row["notes"],
                )
            )
        if not output:
            raise ValueError("production material profile registry is empty")
        return output

    def _load_assets(self) -> list[ProductionAssetRecord]:
        output: list[ProductionAssetRecord] = []
        for row in _read_csv(self.data_dir / "asset_manifest.csv"):
            glb_path = self.package_root / row["glb_path"]
            prelim_renderable = (
                row["production_status"] == "production_ready"
                and _bool(row["redistribution_allowed"])
                and row["source_license_status"] != "pending_rights_review"
                and glb_path.is_file()
            )
            output.append(
                ProductionAssetRecord(
                    asset_id=row["asset_id"],
                    catalog_id=row["catalog_id"],
                    name=row["name"],
                    category=row["category"],
                    glb_path=row["glb_path"],
                    blend_source_path=row["blend_source_path"],
                    dimensions=Dimensions(
                        width_m=float(row["width_m"]),
                        depth_m=float(row["depth_m"]),
                        height_m=float(row["height_m"]),
                    ),
                    anchor_type=row["anchor_type"],
                    scaling_policy=row["scaling_policy"],
                    repeat_axis=row["repeat_axis"],
                    min_uniform_scale=float(row["min_uniform_scale"]),
                    max_uniform_scale=float(row["max_uniform_scale"]),
                    collision_padding_m=float(row["collision_padding_m"]),
                    material_profile_id=row["material_profile_id"],
                    lod0_triangle_budget=int(row["lod0_triangle_budget"]),
                    lod1_triangle_budget=int(row["lod1_triangle_budget"]),
                    lod2_triangle_budget=int(row["lod2_triangle_budget"]),
                    texture_max_px=int(row["texture_max_px"]),
                    source_license_status=row["source_license_status"],
                    redistribution_allowed=_bool(row["redistribution_allowed"]),
                    production_status=row["production_status"],
                    renderable=prelim_renderable,
                )
            )
        if not output:
            raise ValueError("production asset manifest is empty")
        return output

    def _validate_manifest_integrity(self) -> None:
        if len(self.by_asset_id) != len(self.assets):
            raise ValueError("production asset ids must be unique")
        if len(self.by_catalog_id) != len(self.assets):
            raise ValueError("each real catalogue item must map to one v1 asset requirement")
        profile_ids = {profile.profile_id for profile in self.material_profiles}
        for asset in self.assets:
            if asset.material_profile_id not in profile_ids:
                raise ValueError(
                    f"{asset.asset_id} references unknown material profile "
                    f"{asset.material_profile_id}"
                )
            if not asset.glb_path.startswith("app/assets/production/"):
                raise ValueError(
                    f"{asset.asset_id} GLB path must stay inside app/assets/production/"
                )
            if not asset.glb_path.endswith(".glb"):
                raise ValueError(f"{asset.asset_id} GLB path must end with .glb")
            if not asset.blend_source_path.startswith("assets/production_sources/"):
                raise ValueError(
                    f"{asset.asset_id} source path must stay inside assets/production_sources/"
                )
            if asset.min_uniform_scale > asset.max_uniform_scale:
                raise ValueError(f"{asset.asset_id} has an invalid uniform-scale range")
            if asset.max_uniform_scale - asset.min_uniform_scale > 0.10:
                raise ValueError(
                    f"{asset.asset_id} allows excessive uniform scaling; use modular repetition instead"
                )
            if (
                asset.production_status == "production_ready"
                and (
                    not asset.redistribution_allowed
                    or asset.source_license_status == "pending_rights_review"
                )
            ):
                raise ValueError(
                    f"{asset.asset_id} cannot be production_ready before rights are confirmed"
                )

        catalog_ids = {row["item_id"] for row in self.catalog.items}
        mapped_ids = set(self.by_catalog_id)
        missing = sorted(catalog_ids - mapped_ids)
        extras = sorted(mapped_ids - catalog_ids)
        if missing or extras:
            raise ValueError(
                "production asset mapping must exactly cover the real catalogue; "
                f"missing={missing}, extras={extras}"
            )
        for row in self.catalog.items:
            asset = self.by_catalog_id[row["item_id"]]
            expected = (
                int(row["width_cm"]) / 100,
                int(row["depth_cm"]) / 100,
                int(row["height_cm"]) / 100,
            )
            actual = (
                asset.dimensions.width_m,
                asset.dimensions.depth_m or 0.0,
                asset.dimensions.height_m,
            )
            if any(abs(a - b) > 0.001 for a, b in zip(actual, expected, strict=True)):
                raise ValueError(
                    f"{asset.asset_id} true-size dimensions do not match the real catalogue"
                )

    def summary(self) -> ProductionAssetLibrarySummary:
        validations = [
            self.validate_asset(asset.asset_id)
            for asset in self.assets
            if asset.production_status == "production_ready"
        ]
        production_ready = sum(result.status == "ready" for result in validations)
        missing_count = sum(
            not (self.package_root / asset.glb_path).is_file()
            for asset in self.assets
        )
        pending_rights = sum(
            asset.source_license_status == "pending_rights_review"
            for asset in self.assets
        )
        catalog_count = len(self.catalog.items)
        return ProductionAssetLibrarySummary(
            total_asset_requirements=len(self.assets),
            real_catalog_item_count=catalog_count,
            mapped_catalog_item_count=len(self.by_catalog_id),
            material_profile_count=len(self.material_profiles),
            production_ready_count=production_ready,
            missing_glb_count=missing_count,
            pending_rights_review_count=pending_rights,
            library_target_met=production_ready >= 80,
        )

    def catalog_response(self) -> ProductionAssetCatalogResponse:
        return ProductionAssetCatalogResponse(
            summary=self.summary(),
            assets=self.assets,
            material_profiles=self.material_profiles,
            limitations=list(self._limitations),
        )

    def for_catalog_id(self, catalog_id: str) -> ProductionAssetRecord | None:
        return self.by_catalog_id.get(catalog_id)

    def is_renderable_catalog_item(self, catalog_id: str) -> bool:
        asset = self.for_catalog_id(catalog_id)
        if asset is None or asset.production_status != "production_ready":
            return False
        return self.validate_asset(asset.asset_id).status == "ready"

    def customer_glb_path(self, asset_id: str) -> Path:
        record = self.by_asset_id.get(asset_id)
        if record is None:
            raise KeyError(asset_id)
        validation = self.validate_asset(asset_id)
        if validation.status != "ready" or not validation.renderable:
            raise ValueError(
                f"Asset '{asset_id}' has not passed every production and rights gate."
            )
        path = self.package_root / record.glb_path
        if not path.is_file():
            raise ValueError(f"Asset '{asset_id}' production GLB is missing.")
        return path

    def validate_asset(self, asset_id: str) -> ProductionAssetValidationResponse:
        cached = self._validation_cache.get(asset_id)
        if cached is not None:
            return cached
        record = self.by_asset_id.get(asset_id)
        if record is None:
            raise KeyError(asset_id)
        path = self.package_root / record.glb_path
        installation, collision = _physical_envelopes(record)
        if not path.is_file():
            response = ProductionAssetValidationResponse(
                asset_id=record.asset_id,
                catalog_id=record.catalog_id,
                status="missing_glb",
                glb_path=record.glb_path,
                installation_envelope_m=installation,
                collision_envelope_m=collision,
                checks=[],
                errors=[
                    "The production GLB file does not exist yet. Create it from the approved Blender source and run the local validator."
                ],
                warnings=[
                    "Missing planned assets continue to use BakeSmart's procedural planning fallback."
                ],
                renderable=False,
            )
            self._validation_cache[asset_id] = response
            return response

        file_size = path.stat().st_size
        if file_size > MAX_MODULE_FILE_BYTES:
            response = ProductionAssetValidationResponse(
                asset_id=record.asset_id,
                catalog_id=record.catalog_id,
                status="invalid_glb",
                glb_path=record.glb_path,
                file_size_bytes=file_size,
                installation_envelope_m=installation,
                collision_envelope_m=collision,
                errors=[
                    f"Module file exceeds the {MAX_MODULE_FILE_BYTES // (1024 * 1024)} MB mobile budget."
                ],
                warnings=[],
                renderable=False,
            )
            self._validation_cache[asset_id] = response
            return response

        data = path.read_bytes()
        checks, errors, warnings, triangle_count = inspect_glb_bytes(data, record)
        document = _glb_json_document(data)
        try:
            measured = _visible_mesh_dimensions(document) if document is not None else None
        except (TypeError, ValueError):
            measured = None
        visible_values_fit_schema = measured is not None and (
            0 < measured[0] <= 100
            and 0 < measured[1] <= 100
            and 0 < measured[2] <= 30
        )
        visible = (
            Dimensions(width_m=measured[0], depth_m=measured[1], height_m=measured[2])
            if visible_values_fit_schema
            else None
        )
        coverage = (
            AssetBoundsCoverage(
                width_fraction=measured[0] / installation.width_m,
                depth_fraction=measured[1] / (installation.depth_m or 1.0),
                height_fraction=measured[2] / installation.height_m,
            )
            if measured is not None
            else None
        )
        if errors:
            status = "invalid_glb"
        elif (
            record.production_status != "production_ready"
            or not record.redistribution_allowed
            or record.source_license_status == "pending_rights_review"
        ):
            status = "not_approved"
            warnings.append(
                "The binary is structurally acceptable but is not approved for customer rendering until production and rights review are complete."
            )
        else:
            status = "ready"

        response = ProductionAssetValidationResponse(
            asset_id=record.asset_id,
            catalog_id=record.catalog_id,
            status=status,
            glb_path=record.glb_path,
            file_size_bytes=file_size,
            triangle_count=triangle_count,
            installation_envelope_m=installation,
            visible_mesh_bounds_m=visible,
            visible_coverage=coverage,
            collision_envelope_m=collision,
            checks=checks,
            errors=errors,
            warnings=warnings,
            renderable=status == "ready",
        )
        self._validation_cache[asset_id] = response
        return response


production_asset_registry = ProductionAssetRegistry()
