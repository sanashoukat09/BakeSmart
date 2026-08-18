from typing import Literal

from app.schemas.design import DesignRequest, RecommendationResponse


class RecommendationService:
    """Boundary for the self-trained recommendation model.

    Phase 2 deliberately keeps this service unavailable. A later approved phase
    will load BakeSmart's own trained weights and implement ``recommend``.
    """

    @property
    def is_ready(self) -> bool:
        return False

    @property
    def status(self) -> Literal["not_trained", "ready", "error"]:
        return "not_trained"

    def recommend(self, _: DesignRequest) -> RecommendationResponse:
        raise RuntimeError("BakeSmart recommendation model has not been trained")


recommendation_service = RecommendationService()
