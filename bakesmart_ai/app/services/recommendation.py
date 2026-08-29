"""Local model inference and recommendation orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from app.schemas.design import (
    DesignPackageRecommendation,
    DesignRequest,
    PreviewAvailability,
    RecommendationResponse,
)
from app.services.catalog import CatalogStore
from app.services.feature_adapter import RequestFeatureAdapter
from app.services.glb_builder import ProceduralGlbBuilder
from app.services.photo_artifacts import (
    PhotoPreviewStore,
    TemporaryPhotoStore,
    photo_preview_store,
    temporary_photo_store,
)
from app.services.photo_preview_builder import PhotoPreviewBuilder
from app.services.scene_artifacts import SceneArtifactStore
from app.services.scene_builder import SceneBuilder, SceneBuildResult
from app.services.stage3_recommendation import Stage3RecommendationEngine
from training.model_runtime import BootstrapModelRuntime

STAGE3_MODEL_VERSION = "stage3-real-catalog-v1"


class RecommendationService:
    """Load BakeSmart's own checkpoint and build one coordinated scene."""

    def __init__(
        self,
        photo_store: TemporaryPhotoStore = temporary_photo_store,
        preview_store: PhotoPreviewStore = photo_preview_store,
    ) -> None:
        self.runtime: BootstrapModelRuntime | None = None
        self.feature_adapter: RequestFeatureAdapter | None = None
        self.catalog_store: CatalogStore | None = None
        self.scene_builder: SceneBuilder | None = None
        self.stage3_engine: Stage3RecommendationEngine | None = None
        self.glb_builder: ProceduralGlbBuilder | None = None
        self.artifact_store: SceneArtifactStore | None = None
        self.photo_store = photo_store
        self.preview_store = preview_store
        self.photo_preview_builder = PhotoPreviewBuilder()
        self.load_error: str | None = None
        try:
            self.runtime = BootstrapModelRuntime.load()
            self.feature_adapter = RequestFeatureAdapter.load()
            if self.runtime.feature_columns != self.feature_adapter.feature_columns:
                raise ValueError(
                    "model and runtime preprocessing feature orders do not match"
                )
            self.catalog_store = CatalogStore()
            self.scene_builder = SceneBuilder(self.catalog_store)
            self.stage3_engine = Stage3RecommendationEngine()
            self.glb_builder = ProceduralGlbBuilder()
            self.artifact_store = SceneArtifactStore()
        except FileNotFoundError as exc:
            self.load_error = str(exc)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self.load_error = str(exc)

    @property
    def is_ready(self) -> bool:
        return all(
            value is not None
            for value in (
                self.runtime,
                self.feature_adapter,
                self.catalog_store,
                self.scene_builder,
                self.stage3_engine,
                self.glb_builder,
                self.artifact_store,
            )
        )

    @property
    def status(self) -> Literal["not_trained", "ready", "error"]:
        if self.is_ready:
            return "ready"
        if self.load_error and "No such file" in self.load_error:
            return "not_trained"
        return "error"

    def recommend(self, request: DesignRequest) -> RecommendationResponse:
        if not self.is_ready:
            raise RuntimeError(self.load_error or "BakeSmart model is unavailable")
        assert self.runtime is not None
        assert self.feature_adapter is not None
        assert self.catalog_store is not None
        assert self.scene_builder is not None
        assert self.stage3_engine is not None
        assert self.glb_builder is not None
        assert self.artifact_store is not None

        adapted = self.feature_adapter.transform(request)
        model_signals = self.runtime.predict(adapted.matrix)[0]
        bootstrap_results = {
            package_id: self.scene_builder.build(
                request,
                model_signals,
                package_tier=package_id,
            )
            for package_id in ("essential", "balanced", "statement")
        }
        selected_theme_id = bootstrap_results["balanced"].selected_theme_id
        stage3_plans = self.stage3_engine.build_plans(request, selected_theme_id)
        package_results = {
            package_id: self.scene_builder.apply_real_catalogue_plan(
                request,
                bootstrap_results[package_id],
                stage3_plans[package_id].selected,
                stage3_plans[package_id].warnings,
            )
            for package_id in ("essential", "balanced", "statement")
        }
        recommended_package_id = self._recommended_package_id(request)
        result = package_results[recommended_package_id]
        request_json = json.dumps(
            {
                "model_version": STAGE3_MODEL_VERSION,
                "request": request.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        design_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()[:20]
        design_id = f"design-{design_hash}"
        warnings = [*adapted.warnings, *result.warnings]
        scene = result.scene
        preview = result.preview
        try:
            palette = self.catalog_store.themes[result.selected_theme_id]["palette_hex"]
            generated = self.glb_builder.build(
                request,
                scene,
                result.cake,
                palette,
                design_id,
            )
            self.artifact_store.write(design_id, generated.data)
            scene = scene.model_copy(
                update={"asset_status": "generated_procedural_glb"}
            )
            preview = PreviewAvailability(
                interactive_3d_ready=True,
                viewer_3d_url=(
                    f"/viewer/{design_id}?package={recommended_package_id}"
                ),
                viewer_label="Open Basic 3D Layout Preview",
                scene_glb_url=f"/api/v1/designs/{design_id}/scene.glb",
                ar_supported=None,
                ar_url=None,
                fallback_label=None,
            )
            warnings.append(
                "The 3D planning preview uses procedural catalogue-aware geometry in "
                "metre-based scene coordinates. It is not a camera-calibrated photo "
                "reconstruction or a textured PBR asset view."
            )
        except (KeyError, OSError, OverflowError, ValueError):
            warnings.append(
                "Interactive 3D generation failed; use Concept preview—not to scale. "
                "The recommendation and scene specification are still available."
            )
        packages = self._build_packages(
            request=request,
            design_id=design_id,
            results=package_results,
            recommended_package_id=recommended_package_id,
            warnings=warnings,
        )
        return RecommendationResponse(
            design_id=design_id,
            created_at=datetime.now(timezone.utc),
            model_version=STAGE3_MODEL_VERSION,
            model_signals=model_signals,
            selected_theme_id=result.selected_theme_id,
            decorations=result.decorations,
            cake=result.cake,
            costs=result.costs,
            venue_assessment=result.venue_assessment,
            scene=scene,
            preview=preview,
            packages=packages,
            recommended_package_id=recommended_package_id,
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _recommended_package_id(request: DesignRequest) -> str:
        budget = request.decoration_budget_pkr
        guests = request.event.guest_count
        area = request.space.dimensions.width_m * (
            request.space.dimensions.depth_m or 1.0
        )
        if budget >= 70_000 and (guests >= 100 or area >= 30):
            return "statement"
        if budget <= 30_000 or (guests <= 20 and area <= 10):
            return "essential"
        return "balanced"

    def _build_packages(
        self,
        *,
        request: DesignRequest,
        design_id: str,
        results: dict[str, SceneBuildResult],
        recommended_package_id: str,
        warnings: list[str],
    ) -> list[DesignPackageRecommendation]:
        assert self.catalog_store is not None
        package_names = {
            "essential": "Essential Focus",
            "balanced": "Balanced Celebration",
            "statement": "Statement Experience",
        }
        venue_path = None
        for evidence in sorted(
            request.space.photo_evidence,
            key=lambda photo: photo.angle.value != "wide",
        ):
            try:
                venue_path = self.photo_store.existing_path(evidence.photo_id)
            except ValueError:
                venue_path = None
            if venue_path is not None:
                break
        try:
            cake_path = self.photo_store.existing_path(
                request.cake.cake_image_reference
            )
        except ValueError:
            cake_path = None
        packages: list[DesignPackageRecommendation] = []
        for package_id in ("essential", "balanced", "statement"):
            result = results[package_id]
            preview_url = None
            if venue_path is not None and cake_path is not None:
                try:
                    theme = self.catalog_store.themes[result.selected_theme_id]
                    image = self.photo_preview_builder.build(
                        venue_path=venue_path,
                        cake_path=cake_path,
                        request=request,
                        package_id=package_id,
                        package_name=package_names[package_id],
                        selected_theme_id=result.selected_theme_id,
                        decorations=result.decorations,
                        palette_hex=theme["palette_hex"],
                        decoration_cost_pkr=result.costs.decoration_cost_pkr,
                    )
                    preview_id = f"{design_id}-{package_id}"
                    self.preview_store.write(preview_id, image)
                    preview_url = f"/preview/{design_id}/{package_id}"
                    warnings.append(
                        "Stage 5.3 cut-outs represent the selected catalogue categories; "
                        "confirm the exact vendor item before ordering."
                    )
                except (KeyError, OSError, ValueError):
                    warnings.append(
                        f"The {package_names[package_id]} photo preview could not "
                        "be generated."
                    )
            packages.append(
                DesignPackageRecommendation(
                    package_id=package_id,
                    name=package_names[package_id],
                    selected_theme_id=result.selected_theme_id,
                    rationale=self._package_rationale(request, package_id),
                    decorations=result.decorations,
                    decoration_cost_pkr=result.costs.decoration_cost_pkr,
                    cake_cost_pkr=result.costs.cake_cost_pkr,
                    total_cost_pkr=result.costs.total_cost_pkr,
                    budget_pkr=request.decoration_budget_pkr,
                    remaining_budget_pkr=result.costs.remaining_budget_pkr,
                    photo_preview_url=preview_url,
                    recommended=package_id == recommended_package_id,
                )
            )
        if venue_path is None or cake_path is None:
            warnings.append(
                "Photo-based previews were unavailable because a temporary venue or "
                "cake photo had expired or was not uploaded through the Stage 1 API."
            )
        return packages

    @staticmethod
    def _package_rationale(request: DesignRequest, package_id: str) -> str:
        event = request.event.event_type.value.replace("_", " ")
        environment = request.space.environment.value.replace("_", " ")
        colours = (
            ", ".join(request.event.preferred_colors[:3])
            or "the theme palette"
        )
        if package_id == "essential":
            return (
                f"A lower-cost focal setup for this {event}, prioritising the most "
                f"useful pieces in the measured {environment} space and {colours}."
            )
        if package_id == "balanced":
            return (
                f"A fuller {event} setup balancing focal, lighting and supporting "
                f"details for {request.event.guest_count} guests without filling "
                "every area."
            )
        return (
            f"A high-impact {event} package for a larger visual presence, with more "
            f"layers and quantities while respecting the confirmed obstacle map."
        )


recommendation_service = RecommendationService()
