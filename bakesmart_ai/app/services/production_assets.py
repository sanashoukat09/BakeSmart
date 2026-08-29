"""Local production-asset manifest, GLB validation, and readiness checks."""

from __future__ import annotations

import csv
import json
import struct
from pathlib import Path
from typing import Any

from app.schemas.assets import (
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
        "The current customer viewer still renders a single procedural GLB and does not assemble these external modular GLBs yet.",
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

    def validate_asset(self, asset_id: str) -> ProductionAssetValidationResponse:
        cached = self._validation_cache.get(asset_id)
        if cached is not None:
            return cached
        record = self.by_asset_id.get(asset_id)
        if record is None:
            raise KeyError(asset_id)
        path = self.package_root / record.glb_path
        if not path.is_file():
            response = ProductionAssetValidationResponse(
                asset_id=record.asset_id,
                catalog_id=record.catalog_id,
                status="missing_glb",
                glb_path=record.glb_path,
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
            checks=checks,
            errors=errors,
            warnings=warnings,
            renderable=status == "ready",
        )
        self._validation_cache[asset_id] = response
        return response


production_asset_registry = ProductionAssetRegistry()
