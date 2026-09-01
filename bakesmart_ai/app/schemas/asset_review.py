"""Review-only contracts for human inspection of production-candidate GLBs."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.design import Dimensions, StrictModel


ProductionAssetVisualDecision = Literal["approve", "reject", "needs_correction"]


class ProductionAssetReviewDecisionRecord(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    decision: ProductionAssetVisualDecision
    notes: str = Field(default="", max_length=1000)
    reviewed_at: datetime
    artifact_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="Exact GLB revision that received this decision.",
    )
    manifest_changed: Literal[False] = False
    production_promoted: Literal[False] = False


class ProductionAssetReviewCandidate(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    catalog_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    dimensions: Dimensions
    material_profile_id: str = Field(pattern=r"^mat-[a-z0-9]+(?:-[a-z0-9]+)*$")
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    source_license_status: str = Field(min_length=1, max_length=80)
    redistribution_allowed: bool
    production_status: Literal["geometry_review"] = "geometry_review"
    structurally_valid: bool
    triangle_count: int = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    true_size_scale: Literal[1.0] = 1.0
    review_only: Literal[True] = True
    customer_renderable: Literal[False] = False
    glb_url: str = Field(min_length=1, max_length=260)
    decision: ProductionAssetReviewDecisionRecord | None = None


class ProductionAssetReviewListResponse(StrictModel):
    review_version: Literal["production-asset-visual-review-v1"] = (
        "production-asset-visual-review-v1"
    )
    review_only: Literal[True] = True
    production_ready: Literal[False] = False
    candidate_count: int = Field(ge=0, le=200)
    decided_count: int = Field(ge=0, le=200)
    pending_count: int = Field(ge=0, le=200)
    assets: list[ProductionAssetReviewCandidate] = Field(default_factory=list, max_length=200)
    note: str = Field(min_length=1, max_length=500)


class ProductionAssetReviewSubmission(StrictModel):
    asset_id: str = Field(pattern=r"^prod-[a-z0-9]+(?:-[a-z0-9]+)*$")
    decision: ProductionAssetVisualDecision
    notes: str = Field(default="", max_length=1000)


class ProductionAssetReviewSubmissionResponse(StrictModel):
    saved: Literal[True] = True
    record: ProductionAssetReviewDecisionRecord
    message: str = Field(min_length=1, max_length=500)
