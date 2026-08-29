"""Stage 3 catalogue-backed, explainable decoration package planning."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.design import DesignRequest
from app.services.production_assets import (
    ProductionAssetRegistry,
    production_asset_registry,
)
from app.services.real_decor_catalog import RealDecorCatalog
from app.services.scene_builder import CATEGORY_ALIASES, EVENT_DECOR_PRIORITY


PACKAGE_BUDGET_SHARE = {"essential": 0.52, "balanced": 0.78, "statement": 1.0}
PACKAGE_CATEGORY_TARGET = {"essential": 2, "balanced": 4, "statement": 5}
TIER_SCORE = {
    "essential": {"essential": 5, "balanced": 2, "statement": 0},
    "balanced": {"essential": 2, "balanced": 5, "statement": 2},
    "statement": {"essential": 0, "balanced": 3, "statement": 6},
}


@dataclass(frozen=True)
class Stage3Plan:
    package_id: str
    selected: tuple[tuple[dict[str, str], int, int], ...]
    budget_limit_pkr: int
    warnings: tuple[str, ...]


class Stage3RecommendationEngine:
    """Rank real catalogue components and prefer validated production GLBs."""

    def __init__(
        self,
        catalog: RealDecorCatalog | None = None,
        assets: ProductionAssetRegistry | None = None,
    ) -> None:
        self.catalog = catalog or RealDecorCatalog()
        self.assets = assets or production_asset_registry

    def build_plans(
        self, request: DesignRequest, selected_theme_id: str
    ) -> dict[str, Stage3Plan]:
        selection = self.catalog.filter_items(
            event_type=request.event.event_type.value,
            theme_id=selected_theme_id,
            environment=request.space.environment.value,
        )
        return {
            package_id: self._build_plan(
                request, selected_theme_id, package_id, selection.items
            )
            for package_id in ("essential", "balanced", "statement")
        }

    def _build_plan(
        self,
        request: DesignRequest,
        theme_id: str,
        package_id: str,
        candidates: tuple[dict[str, str], ...],
    ) -> Stage3Plan:
        budget_limit = int(
            request.decoration_budget_pkr * PACKAGE_BUDGET_SHARE[package_id]
        )
        required = [
            CATEGORY_ALIASES.get(value, value)
            for value in request.event.required_decor_categories
        ]
        excluded = {
            CATEGORY_ALIASES.get(value, value)
            for value in request.event.excluded_decor_categories
        }
        event_order = EVENT_DECOR_PRIORITY[request.event.event_type.value]
        category_order = list(dict.fromkeys([*required, *event_order]))
        category_target = max(PACKAGE_CATEGORY_TARGET[package_id], len(required))
        selected: list[tuple[dict[str, str], int, int]] = []
        spent = 0
        warnings: list[str] = []
        used_ids: set[str] = set()

        for category in category_order:
            if len(selected) >= category_target:
                break
            if category in excluded:
                if category in required:
                    warnings.append(
                        f"Required category '{category}' was also excluded and was not selected."
                    )
                continue
            ranked = sorted(
                (
                    row for row in candidates
                    if row["category"] == category
                    and row["item_id"] not in used_ids
                    and self._fits_space(row, request)
                    and not self._uses_excluded_colour(row, request)
                ),
                key=lambda row: self._rank_key(
                    row, request, theme_id, package_id, event_order
                ),
            )
            picked = None
            for row in ranked:
                unit_cost = self._planning_price(row, package_id)
                quantity = self._quantity(row, request, package_id)
                while quantity > int(row["quantity_min"]) and (
                    spent + quantity * unit_cost > budget_limit
                ):
                    quantity -= 1
                if spent + quantity * unit_cost <= budget_limit:
                    picked = row, quantity, unit_cost
                    break
            if picked is None:
                if category in required:
                    warnings.append(
                        f"Required category '{category}' did not fit the real-catalogue budget, venue, colour, or safety filters."
                    )
                continue
            row, quantity, unit_cost = picked
            selected.append(
                (self._adapt_row(row, request, package_id), quantity, unit_cost)
            )
            used_ids.add(row["item_id"])
            spent += quantity * unit_cost

        if not selected:
            warnings.append(
                "No real catalogue component fit this package's budget and venue constraints."
            )
        else:
            fallback_count = sum(
                not self.assets.is_renderable_catalog_item(row["decor_id"])
                for row, _, _ in selected
            )
            if fallback_count:
                warnings.append(
                    f"{fallback_count} selected catalogue component(s) still use procedural 3D fallback because their modular production GLBs are not yet approved."
                )
        return Stage3Plan(package_id, tuple(selected), budget_limit, tuple(warnings))

    def _rank_key(
        self,
        row: dict[str, str],
        request: DesignRequest,
        theme_id: str,
        package_id: str,
        event_order: tuple[str, ...],
    ) -> tuple[float, int, str]:
        score = float(TIER_SCORE[package_id][row["package_tier"]])
        themes = set(row["theme_ids"].split(";"))
        if theme_id in themes:
            score += 5
        colours = {value.lower() for value in row["color_tags"].split(";")}
        preferred = {
            token
            for value in request.event.preferred_colors
            for token in value.lower().replace("-", " ").split()
        }
        score += 2 * sum(
            any(token in colour.replace("-", " ").split() for colour in colours)
            for token in preferred
        )
        score += max(0, 3 - event_order.index(row["category"]))
        source = self.catalog.market_sources[row["market_source_id"]]
        if source["evidence_type"].startswith("direct_vendor"):
            score += 1
        if self.assets.is_renderable_catalog_item(row["item_id"]):
            score += 8
        return (-score, self._planning_price(row, package_id), row["item_id"])

    @staticmethod
    def _planning_price(row: dict[str, str], package_id: str) -> int:
        low, high = int(row["price_min_pkr"]), int(row["price_max_pkr"])
        fraction = {"essential": 0.0, "balanced": 0.5, "statement": 0.0}[package_id]
        return int(round(low + (high - low) * fraction))

    @staticmethod
    def _quantity(
        row: dict[str, str], request: DesignRequest, package_id: str
    ) -> int:
        low, high = int(row["quantity_min"]), int(row["quantity_max"])
        desired = low
        if package_id == "balanced" and row["category"] in {
            "lighting",
            "floor-arrangement",
        }:
            desired += 1
        if package_id == "statement":
            desired += 2 if row["category"] == "lighting" else 0
        if request.event.guest_count >= 100 and package_id != "essential":
            desired += 1
        return min(high, desired)

    @staticmethod
    def _fits_space(row: dict[str, str], request: DesignRequest) -> bool:
        dimensions = request.space.dimensions
        if int(row["width_cm"]) / 100 > dimensions.width_m:
            return False
        if int(row["height_cm"]) / 100 > dimensions.height_m:
            return False
        if dimensions.depth_m is not None:
            safety_clearance = int(row["required_clearance_cm"]) / 100
            needed_depth = int(row["depth_cm"]) / 100 + max(
                request.minimum_clearance_m,
                safety_clearance,
            )
            if row["placement_zone"] != "tabletop" and needed_depth > dimensions.depth_m:
                return False
        return True

    @staticmethod
    def _uses_excluded_colour(row: dict[str, str], request: DesignRequest) -> bool:
        excluded = " ".join(request.event.excluded_colors).lower().replace("-", " ")
        return any(
            colour.replace("-", " ") in excluded
            for colour in row["color_tags"].lower().split(";")
            if colour not in {"custom", "brand-color"}
        )

    def _adapt_row(
        self, row: dict[str, str], request: DesignRequest, package_id: str
    ) -> dict[str, str]:
        evidence = self.catalog.evidence_for(row)
        safety = evidence["safety_profile"]
        source = evidence["market_source"]
        preferred = (
            ", ".join(request.event.preferred_colors[:3]) or "the chosen palette"
        )
        production_note = ""
        if self.assets.is_renderable_catalog_item(row["item_id"]):
            production_note = (
                " A validated, rights-cleared production GLB is available for this "
                "catalogue item."
            )
        reason = (
            f"Selected for the {package_id} package because it matches the "
            f"{request.event.event_type.value.replace('_', ' ')} event, {preferred}, "
            f"the {request.space.environment.value.replace('_', ' ')} venue and "
            "the available budget. "
            f"Price range evidence: {source['publisher']}."
            f"{production_note}"
        )
        return {
            **row,
            "decor_id": row["item_id"],
            "item_name": row["name"],
            "ar_asset_key": f"real-catalog/{row['item_id']}",
            "safety_notes": safety["rules"],
            "reason": reason,
        }
