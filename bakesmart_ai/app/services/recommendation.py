"""Local model inference and recommendation orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from app.schemas.design import DesignRequest, RecommendationResponse
from app.services.catalog import CatalogStore
from app.services.feature_adapter import RequestFeatureAdapter
from app.services.scene_builder import SceneBuilder
from training.model_runtime import BootstrapModelRuntime


class RecommendationService:
    """Load BakeSmart's own checkpoint and build one coordinated scene."""

    def __init__(self) -> None:
        self.runtime: BootstrapModelRuntime | None = None
        self.feature_adapter: RequestFeatureAdapter | None = None
        self.scene_builder: SceneBuilder | None = None
        self.load_error: str | None = None
        try:
            self.runtime = BootstrapModelRuntime.load()
            self.feature_adapter = RequestFeatureAdapter.load()
            if self.runtime.feature_columns != self.feature_adapter.feature_columns:
                raise ValueError(
                    "model and runtime preprocessing feature orders do not match"
                )
            self.scene_builder = SceneBuilder(CatalogStore())
        except FileNotFoundError as exc:
            self.load_error = str(exc)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self.load_error = str(exc)

    @property
    def is_ready(self) -> bool:
        return all(
            value is not None
            for value in (self.runtime, self.feature_adapter, self.scene_builder)
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
        assert self.scene_builder is not None

        adapted = self.feature_adapter.transform(request)
        model_signals = self.runtime.predict(adapted.matrix)[0]
        result = self.scene_builder.build(request, model_signals)
        request_json = json.dumps(
            {
                "model_version": self.runtime.metadata["model_version"],
                "request": request.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        design_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()[:20]
        warnings = [*adapted.warnings, *result.warnings]
        return RecommendationResponse(
            design_id=f"design-{design_hash}",
            created_at=datetime.now(timezone.utc),
            model_version=str(self.runtime.metadata["model_version"]),
            model_signals=model_signals,
            selected_theme_id=result.selected_theme_id,
            decorations=result.decorations,
            cake=result.cake,
            costs=result.costs,
            scene=result.scene,
            preview=result.preview,
            warnings=list(dict.fromkeys(warnings)),
        )


recommendation_service = RecommendationService()
