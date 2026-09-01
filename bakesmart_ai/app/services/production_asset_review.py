"""Human visual-review queue for structurally valid production-candidate GLBs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.asset_review import (
    ProductionAssetReviewCandidate,
    ProductionAssetReviewDecisionRecord,
    ProductionAssetReviewListResponse,
    ProductionAssetReviewSubmission,
    ProductionAssetReviewSubmissionResponse,
)
from app.services.production_assets import (
    ProductionAssetRegistry,
    inspect_glb_bytes,
    production_asset_registry,
)


class ProductionAssetReviewService:
    """Expose geometry-review assets without promoting them to production-ready."""

    def __init__(
        self,
        registry: ProductionAssetRegistry = production_asset_registry,
        review_path: Path | None = None,
    ) -> None:
        self.registry = registry
        self.review_path = review_path or (
            self.registry.data_dir / "visual_review_decisions.json"
        )
        self.build_report_path = (
            self.registry.data_dir / "production_candidate_build_report.json"
        )
        self.validation_report_path = (
            self.registry.data_dir / "production_candidate_validation_report.json"
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object in {path.name}.")
        return value

    def _decisions(self) -> dict[str, ProductionAssetReviewDecisionRecord]:
        raw = self._read_json(self.review_path)
        rows = raw.get("decisions", {})
        if not isinstance(rows, dict):
            raise ValueError("visual review decision ledger must contain an object map")
        output: dict[str, ProductionAssetReviewDecisionRecord] = {}
        for asset_id, row in rows.items():
            if isinstance(row, dict):
                output[asset_id] = ProductionAssetReviewDecisionRecord.model_validate(row)
        return output

    def _candidate_payloads(self) -> list[dict[str, Any]]:
        build = self._read_json(self.build_report_path)
        built = {
            row.get("asset_id"): row
            for row in build.get("assets", [])
            if isinstance(row, dict) and row.get("asset_id")
        }
        output: list[dict[str, Any]] = []
        for asset in self.registry.assets:
            if asset.production_status != "geometry_review":
                continue
            build_row = built.get(asset.asset_id)
            if not isinstance(build_row, dict):
                continue
            if not asset.redistribution_allowed:
                continue
            if asset.source_license_status == "pending_rights_review":
                continue
            path = self.registry.package_root / asset.glb_path
            if not path.is_file():
                continue
            checks, errors, warnings, triangles = inspect_glb_bytes(
                path.read_bytes(),
                asset,
            )
            if errors or not checks:
                continue
            output.append(
                {
                    "record": asset,
                    "build": build_row,
                    "path": path,
                    "fresh_validation": {
                        "checks": checks,
                        "warnings": warnings,
                        "triangle_count": triangles,
                        "file_size_bytes": path.stat().st_size,
                    },
                }
            )
        return output

    def _payload_for(self, asset_id: str) -> dict[str, Any]:
        for payload in self._candidate_payloads():
            if payload["record"].asset_id == asset_id:
                return payload
        if asset_id not in self.registry.by_asset_id:
            raise KeyError(asset_id)
        raise ValueError(
            f"Asset '{asset_id}' is not an eligible geometry-review production candidate."
        )

    def candidates(self) -> ProductionAssetReviewListResponse:
        decisions = self._decisions()
        candidates: list[ProductionAssetReviewCandidate] = []
        for payload in self._candidate_payloads():
            asset = payload["record"]
            build = payload["build"]
            fresh_validation = payload["fresh_validation"]
            artifact_sha256 = hashlib.sha256(payload["path"].read_bytes()).hexdigest()
            decision = decisions.get(asset.asset_id)
            if decision is not None and decision.artifact_sha256 != artifact_sha256:
                decision = None
            candidates.append(
                ProductionAssetReviewCandidate(
                    asset_id=asset.asset_id,
                    catalog_id=asset.catalog_id,
                    name=asset.name,
                    category=asset.category,
                    dimensions=asset.dimensions,
                    material_profile_id=asset.material_profile_id,
                    source_ids=[str(value) for value in build.get("source_ids", [])],
                    source_license_status=asset.source_license_status,
                    redistribution_allowed=asset.redistribution_allowed,
                    structurally_valid=True,
                    triangle_count=int(fresh_validation.get("triangle_count") or 0),
                    file_size_bytes=int(fresh_validation["file_size_bytes"]),
                    artifact_sha256=artifact_sha256,
                    glb_url=f"/api/v1/assets/3d/production-review/{asset.asset_id}.glb",
                    decision=decision,
                )
            )
        decided = sum(1 for candidate in candidates if candidate.decision is not None)
        return ProductionAssetReviewListResponse(
            candidate_count=len(candidates),
            decided_count=decided,
            pending_count=len(candidates) - decided,
            assets=candidates,
            note=(
                "Visual decisions are review evidence only. Approve does not alter the "
                "production manifest or make an asset customer-renderable."
            ),
        )

    def glb_path(self, asset_id: str) -> Path:
        payload = self._payload_for(asset_id)
        asset = payload["record"]
        path: Path = payload["path"]
        checks, errors, _, _ = inspect_glb_bytes(path.read_bytes(), asset)
        if errors or not checks:
            raise ValueError(
                f"Asset '{asset_id}' failed structural re-validation: "
                + "; ".join(errors or ["no validation checks were produced"])
            )
        return path

    def submit(
        self,
        submission: ProductionAssetReviewSubmission,
    ) -> ProductionAssetReviewSubmissionResponse:
        candidate_payload = self._payload_for(submission.asset_id)
        notes = submission.notes.strip()
        if submission.decision in {"reject", "needs_correction"} and not notes:
            raise ValueError(
                "Reject and needs_correction decisions require a short reviewer note."
            )
        record = ProductionAssetReviewDecisionRecord(
            asset_id=submission.asset_id,
            decision=submission.decision,
            notes=notes,
            reviewed_at=datetime.now(timezone.utc),
            artifact_sha256=hashlib.sha256(
                candidate_payload["path"].read_bytes()
            ).hexdigest(),
        )
        decisions = self._decisions()
        decisions[submission.asset_id] = record
        payload = {
            "review_version": "production-asset-visual-review-v1",
            "review_only": True,
            "production_ready": False,
            "decisions": {
                asset_id: decision.model_dump(mode="json")
                for asset_id, decision in sorted(decisions.items())
            },
        }
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.review_path.with_suffix(self.review_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.review_path)
        return ProductionAssetReviewSubmissionResponse(
            record=record,
            message=(
                "Review decision saved locally. The production manifest was not changed "
                "and the asset remains non-customer-renderable."
            ),
        )


production_asset_review_service = ProductionAssetReviewService()
