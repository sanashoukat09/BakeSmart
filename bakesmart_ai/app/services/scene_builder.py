"""Budget-aware catalogue selection and combined BakeSmart scene assembly."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.schemas.design import (
    CakePlacement,
    CostBreakdown,
    DecorRecommendation,
    DesignRequest,
    Dimensions,
    ObjectPlacement,
    Position3D,
    PreviewAvailability,
    SceneSpecification,
    VenueAssessment,
)
from app.services.catalog import CatalogStore


THEME_FALLBACKS = {
    "colourful_cartoon": "whimsical-kids",
    "elegant_gold": "glam-gold",
    "modern_minimal": "modern-minimalist",
    "pastel_floral": "floral-romantic",
    "rustic_natural": "rustic-boho",
    "traditional_luxury": "south-asian-wedding",
}

CATEGORY_ALIASES = {
    "cake-table": "table-setting",
    "cake_table": "table-setting",
    "floor_arrangement": "floor-arrangement",
}

# These values are explicitly synthetic planning assumptions, never vendor prices.
PLANNING_UNIT_COST_PKR = {
    "backdrop": 15_000,
    "floor-arrangement": 4_500,
    "lighting": 3_500,
    "table-setting": 3_500,
    "signage": 2_500,
}

DECOR_PRIORITY = {
    "balloon_setup": (
        "backdrop",
        "floor-arrangement",
        "signage",
        "lighting",
        "table-setting",
    ),
    "flower_wall": (
        "floor-arrangement",
        "backdrop",
        "lighting",
        "table-setting",
        "signage",
    ),
    "luxury_stage": (
        "backdrop",
        "lighting",
        "floor-arrangement",
        "table-setting",
        "signage",
    ),
    "minimal_backdrop": (
        "backdrop",
        "table-setting",
        "signage",
        "lighting",
        "floor-arrangement",
    ),
    "rustic_wood_setup": (
        "floor-arrangement",
        "backdrop",
        "signage",
        "lighting",
        "table-setting",
    ),
}


@dataclass(frozen=True)
class SceneBuildResult:
    selected_theme_id: str
    decorations: list[DecorRecommendation]
    cake: CakePlacement
    costs: CostBreakdown
    venue_assessment: VenueAssessment
    scene: SceneSpecification
    preview: PreviewAvailability
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FocalPlacement:
    center_x_m: float
    candidate_available: bool
    walkway_clear: bool
    available_front_clearance_m: float
    blocking_obstacles: tuple[str, ...]


class SceneBuilder:
    def __init__(self, catalog: CatalogStore) -> None:
        self.catalog = catalog

    def build(
        self,
        request: DesignRequest,
        model_signals: dict[str, dict[str, float | str]],
    ) -> SceneBuildResult:
        warnings = [
            "The bootstrap model was trained on synthetic labels and is not production-approved.",
            "All prices are synthetic planning estimates, not vendor or bakery quotes.",
            (
                "The interactive scene uses procedural placeholder geometry; detailed "
                "catalogue art assets are not available yet."
            ),
            (
                "The supplied cake image is retained as a design reference; the "
                "procedural renderer does not reconstruct it as 3D geometry."
            ),
        ]
        selected_theme = self._select_theme(request, model_signals, warnings)
        decor_rows = self.catalog.decor_for(
            selected_theme,
            request.event.event_type.value,
            request.space.environment.value,
        )
        selected_decor = self._select_decor(
            request,
            decor_rows,
            str(model_signals["decor"]["label"]),
            warnings,
        )
        cake_row = self._select_cake(
            request,
            selected_theme,
            str(model_signals["cake"]["label"]),
            warnings,
        )
        for row, _, _ in selected_decor:
            warnings.append(f"Safety for {row['item_name']}: {row['safety_notes']}")
        warnings.extend(
            [
                f"Cake structure: {cake_row['structural_notes']}",
                f"Cake allergens: {cake_row['allergen_notes']}",
            ]
        )
        if not request.space.obstacle_map_confirmed:
            warnings.append(
                "The obstacle map was not customer-confirmed, so doors, windows "
                "and circulation still require visual confirmation."
            )
        if request.space.known_reference_m is None:
            warnings.append(
                "No known reference measurement was supplied; preview scale cannot "
                "be visually verified."
            )
        if not request.space.photo_evidence:
            warnings.append(
                "No locally analysed venue photo evidence was supplied; placement "
                "uses measurements only."
            )
        manual_outlet_count = sum(
            len(photo.manual_outlets) for photo in request.space.photo_evidence
        )
        measured_outlet_count = sum(
            obstacle.obstacle_type.value == "outlet"
            for obstacle in request.space.obstacles
        )
        if manual_outlet_count and not measured_outlet_count:
            warnings.append(
                "Manual Outlet marks identify photo positions only. Add each relevant "
                "Outlet as a measured obstacle before relying on exact clearance."
            )

        table_dimensions = self._table_dimensions(request)
        geometry_verified = self._geometry_is_plausible(
            request, table_dimensions, warnings
        )
        focal = self._focal_placement(
            request,
            table_dimensions,
            any(row["category"] == "backdrop" for row, _, _ in selected_decor),
            warnings,
        )
        decorations, decor_objects, decoration_cost = self._place_decor(
            request,
            selected_decor,
            focal.center_x_m,
            table_dimensions,
        )
        cake, cake_objects, cake_cost = self._place_cake(
            request,
            cake_row,
            focal.center_x_m,
            table_dimensions,
        )
        all_objects = [*cake_objects, *decor_objects]
        venue_assessment = self._venue_assessment(request, focal)
        concept_not_to_scale = (
            request.space.known_reference_m is None
            or not request.space.photo_evidence
            or not request.space.obstacle_map_confirmed
            or not focal.candidate_available
            or not focal.walkway_clear
            or not geometry_verified
            or request.space.dimensions.depth_m is None
        )
        layers = ["cake_and_baked_items", "dessert_table"]
        roles = {item.role for item in all_objects}
        if "decoration" in roles or "signage" in roles:
            layers.append("decorations")
        if "backdrop" in roles:
            layers.append("backdrop")
        if "lighting" in roles:
            layers.append("lighting")

        costs = CostBreakdown(
            decoration_cost_pkr=decoration_cost,
            cake_cost_pkr=cake_cost,
            total_cost_pkr=decoration_cost + cake_cost,
            budget_pkr=request.decoration_budget_pkr,
            remaining_budget_pkr=request.decoration_budget_pkr - decoration_cost,
            budget_scope="decorations_only",
            pricing_basis="synthetic_planning_estimate_not_vendor_quote",
        )
        scene = SceneSpecification(
            space=request.space,
            objects=all_objects,
            minimum_clearance_m=request.minimum_clearance_m,
            concept_not_to_scale=concept_not_to_scale,
            layout_strategy=str(model_signals["layout"]["label"]),
            asset_status="catalog_references_require_3d_asset_creation",
            layers=layers,
        )
        preview = PreviewAvailability(
            interactive_3d_ready=False,
            viewer_3d_url=None,
            viewer_label=None,
            scene_glb_url=None,
            ar_supported=None,
            ar_url=None,
            fallback_label="Concept preview—not to scale",
        )
        if not decorations:
            warnings.append(
                "No compatible decoration package fit the supplied planning budget and filters."
            )
        return SceneBuildResult(
            selected_theme,
            decorations,
            cake,
            costs,
            venue_assessment,
            scene,
            preview,
            tuple(dict.fromkeys(warnings)),
        )

    def _select_theme(
        self,
        request: DesignRequest,
        model_signals: dict[str, dict[str, float | str]],
        warnings: list[str],
    ) -> str:
        requested = request.event.theme_id
        if self.catalog.has_theme(requested):
            return requested
        predicted = str(model_signals["theme"]["label"])
        fallback = THEME_FALLBACKS[predicted]
        warnings.append(
            f"Theme '{requested}' is not in the local catalogue; '{fallback}' was "
            "used as a model-guided fallback."
        )
        return fallback

    def _select_decor(
        self,
        request: DesignRequest,
        candidates: list[dict[str, str]],
        decor_label: str,
        warnings: list[str],
    ) -> list[tuple[dict[str, str], int, int]]:
        by_category = {row["category"]: row for row in candidates}
        required = [
            CATEGORY_ALIASES.get(value, value)
            for value in request.event.required_decor_categories
        ]
        excluded = {
            CATEGORY_ALIASES.get(value, value)
            for value in request.event.excluded_decor_categories
        }
        order = list(dict.fromkeys([*required, *DECOR_PRIORITY.get(decor_label, ())]))
        selected: list[tuple[dict[str, str], int, int]] = []
        spent = 0
        for category in order:
            if category in excluded:
                if category in required:
                    warnings.append(
                        f"Required category '{category}' was also excluded and was not selected."
                    )
                continue
            row = by_category.get(category)
            if row is None:
                if category in required:
                    warnings.append(
                        f"Required category '{category}' has no compatible catalogue item."
                    )
                continue
            quantity = self._quantity_for(category, request)
            unit_cost = PLANNING_UNIT_COST_PKR[category]
            while (
                quantity > 1
                and spent + quantity * unit_cost > request.decoration_budget_pkr
            ):
                quantity -= 1
            item_cost = quantity * unit_cost
            if spent + item_cost > request.decoration_budget_pkr:
                if category in required:
                    warnings.append(
                        f"Required category '{category}' did not fit the supplied "
                        "decoration budget."
                    )
                continue
            selected.append((row, quantity, unit_cost))
            spent += item_cost
        return selected

    @staticmethod
    def _quantity_for(category: str, request: DesignRequest) -> int:
        if category == "floor-arrangement":
            return 2
        if category == "lighting":
            return max(1, min(4, math.ceil(request.space.dimensions.width_m / 2)))
        return 1

    def _select_cake(
        self,
        request: DesignRequest,
        theme_id: str,
        cake_label: str,
        warnings: list[str],
    ) -> dict[str, str]:
        candidates = self.catalog.cakes_for(theme_id, request.event.event_type.value)
        if not candidates:
            candidates = [
                row for row in self.catalog.cakes if row["theme_id"] == theme_id
            ]
            warnings.append(
                "No cake design matched both theme and event; the closest theme cake was used."
            )
        if not candidates:
            raise ValueError(f"no cake catalogue entries exist for theme '{theme_id}'")

        def score(row: dict[str, str]) -> tuple[float, str]:
            value = 0.0
            if row["shape"] == request.cake.shape.value:
                value += 4
            tier_min, tier_max = self._range(row["suggested_tiers"])
            if tier_min <= request.cake.tiers <= tier_max:
                value += 3
            serving_min, serving_max = self._range(row["serving_range"])
            servings = request.cake.servings_required
            if serving_min <= servings <= serving_max:
                value += 4
            else:
                value -= (
                    min(abs(servings - serving_min), abs(servings - serving_max)) / 100
                )
            if cake_label.startswith("three"):
                expected_tier = 3
            elif cake_label.startswith("two"):
                expected_tier = 2
            else:
                expected_tier = 1
            if tier_min <= expected_tier <= tier_max:
                value += 1
            return value, row["cake_design_id"]

        return max(candidates, key=score)

    @staticmethod
    def _range(value: str) -> tuple[int, int]:
        if "-" not in value:
            parsed = int(value)
            return parsed, parsed
        start, end = value.split("-", 1)
        return int(start), int(end)

    @staticmethod
    def _table_dimensions(request: DesignRequest) -> Dimensions:
        width = min(1.5, max(0.01, request.space.dimensions.width_m * 0.8))
        return Dimensions(width_m=width, depth_m=0.75, height_m=0.9)

    @staticmethod
    def _geometry_is_plausible(
        request: DesignRequest,
        table_dimensions: Dimensions,
        warnings: list[str],
    ) -> bool:
        cake_width = request.cake.diameter_m or request.cake.width_m or 0.3
        cake_depth = request.cake.diameter_m or request.cake.depth_m or cake_width
        fits = (
            cake_width <= table_dimensions.width_m
            and cake_depth <= (table_dimensions.depth_m or 0)
            and table_dimensions.height_m + request.cake.height_m
            <= request.space.dimensions.height_m
        )
        if not fits:
            warnings.append(
                "The supplied cake dimensions do not fit the provisional table or "
                "available height; manual sizing is required."
            )
        return fits

    def _focal_placement(
        self,
        request: DesignRequest,
        table_dimensions: Dimensions,
        has_backdrop: bool,
        warnings: list[str],
    ) -> FocalPlacement:
        width = request.space.dimensions.width_m
        available_width = max(0.01, width - 0.01)
        desired_width = max(
            table_dimensions.width_m,
            2.0 if has_backdrop else 1.0,
        )
        setup_width = min(available_width, desired_width)
        candidates = [width * 0.5, width * 0.35, width * 0.65]
        blocking: list[str] = []
        for center in candidates:
            if center - setup_width / 2 < 0 or center + setup_width / 2 > width:
                continue
            intersections = [
                obstacle
                for obstacle in request.space.obstacles
                if self._intersects_setup(
                    center,
                    setup_width,
                    obstacle.position.x_m,
                    obstacle.position.y_m,
                    obstacle.dimensions.width_m,
                    obstacle.dimensions.depth_m or 0.2,
                    request.minimum_clearance_m,
                )
            ]
            if not intersections:
                available_clearance = self._available_front_clearance(request)
                walkway_clear = available_clearance >= request.minimum_clearance_m
                if not walkway_clear:
                    warnings.append(
                        "The measured depth does not verify the requested clear "
                        "circulation in front of the setup."
                    )
                return FocalPlacement(
                    center_x_m=center,
                    candidate_available=True,
                    walkway_clear=walkway_clear,
                    available_front_clearance_m=available_clearance,
                    blocking_obstacles=(),
                )
            blocking.extend(
                obstacle.label or obstacle.obstacle_type.value
                for obstacle in intersections
            )
        warnings.append(
            "No obstacle-free focal position could be verified; manual placement "
            "review is required."
        )
        return FocalPlacement(
            center_x_m=width * 0.5,
            candidate_available=False,
            walkway_clear=False,
            available_front_clearance_m=self._available_front_clearance(request),
            blocking_obstacles=tuple(dict.fromkeys(blocking)),
        )

    @staticmethod
    def _intersects_setup(
        center: float,
        setup_width: float,
        obstacle_x: float,
        obstacle_y: float,
        obstacle_width: float,
        obstacle_depth: float,
        clearance: float,
    ) -> bool:
        setup_left = center - setup_width / 2
        setup_right = center + setup_width / 2
        setup_back = 0.0
        setup_front = 1.0
        obstacle_left = obstacle_x - clearance
        obstacle_right = obstacle_x + obstacle_width + clearance
        obstacle_back = obstacle_y - clearance
        obstacle_front = obstacle_y + obstacle_depth + clearance
        return not (
            setup_right <= obstacle_left
            or setup_left >= obstacle_right
            or setup_front <= obstacle_back
            or setup_back >= obstacle_front
        )

    @staticmethod
    def _available_front_clearance(request: DesignRequest) -> float:
        depth = request.space.dimensions.depth_m
        if depth is None:
            return 0.0
        return max(0.0, depth - (0.45 + 0.75 / 2))

    @staticmethod
    def _venue_assessment(
        request: DesignRequest,
        focal: FocalPlacement,
    ) -> VenueAssessment:
        photos = request.space.photo_evidence
        verified = (
            request.space.obstacle_map_confirmed
            and focal.candidate_available
            and focal.walkway_clear
        )
        has_second_angle = any(photo.angle.value == "second_angle" for photo in photos)
        photo_quality_ok = bool(photos) and all(
            photo.quality.value != "low" for photo in photos
        )
        if (
            verified
            and len(photos) == 2
            and has_second_angle
            and photo_quality_ok
            and request.space.known_reference_m is not None
        ):
            confidence = "high"
        elif verified and photos and request.space.known_reference_m is not None:
            confidence = "medium"
        else:
            confidence = "low"

        observed_facts = [
            f"{len(photos)} venue photo angle(s) were analysed locally.",
            (
                f"The customer confirmed {len(request.space.obstacles)} obstacle(s)."
                if request.space.obstacle_map_confirmed
                else "The customer has not confirmed the obstacle map."
            ),
            (
                "The measured depth leaves "
                f"{focal.available_front_clearance_m:.2f} m in front of the setup."
            ),
        ]
        for photo in photos:
            angle_label = photo.angle.value.replace("_", " ")
            observed_facts.extend(
                f"{angle_label.title()}: {observation}"
                for observation in photo.observations
            )
            if photo.manual_outlets:
                observed_facts.append(
                    f"{angle_label.title()}: the customer manually marked "
                    f"{len(photo.manual_outlets)} visible Outlet position(s)."
                )
        assumptions: list[str] = []
        if not photos:
            assumptions.append("The venue appearance was not checked from a photo.")
        if photos and not has_second_angle:
            assumptions.append("Areas outside the single photo angle remain unknown.")
        candidate_labels = sorted(
            {
                candidate.label
                for photo in photos
                for candidate in photo.unconfirmed_candidates
            }
        )
        if candidate_labels:
            assumptions.append(
                "Local vision suggested possible "
                f"{', '.join(candidate_labels)} region(s); none were used as "
                "confirmed obstacles."
            )
        manual_outlet_count = sum(len(photo.manual_outlets) for photo in photos)
        measured_outlet_count = sum(
            obstacle.obstacle_type.value == "outlet"
            for obstacle in request.space.obstacles
        )
        if manual_outlet_count and not measured_outlet_count:
            assumptions.append(
                "Manual Outlet marks are normalized photo positions, not measured 3D "
                "obstacles; exact Outlet clearance remains unverified."
            )
        if not request.space.obstacle_map_confirmed:
            assumptions.append(
                "Unlisted doors, furniture, outlets, or walkways may exist."
            )
        if request.space.known_reference_m is None:
            assumptions.append(
                "Photo scale is unverified because no known reference was supplied."
            )
        assumptions.append(
            "Photo analysis does not automatically identify safety-critical objects."
        )
        return VenueAssessment(
            photo_count=len(photos),
            evidence_confidence=confidence,
            placement_status=(
                "clearance_verified" if verified else "manual_review_required"
            ),
            scale_source=(
                "user_confirmed_measurements"
                if request.space.known_reference_m is not None
                else "unverified"
            ),
            selected_focal_center_x_m=round(focal.center_x_m, 3),
            available_front_clearance_m=round(
                focal.available_front_clearance_m,
                3,
            ),
            minimum_clearance_m=request.minimum_clearance_m,
            obstacle_count=len(request.space.obstacles),
            obstacle_map_confirmed=request.space.obstacle_map_confirmed,
            blocking_obstacles=list(focal.blocking_obstacles),
            observed_facts=observed_facts,
            assumptions=assumptions,
        )

    def _place_cake(
        self,
        request: DesignRequest,
        cake_row: dict[str, str],
        center: float,
        table_dimensions: Dimensions,
    ) -> tuple[CakePlacement, list[ObjectPlacement], int]:
        table = ObjectPlacement(
            asset_id="builtin/cake-table",
            role="cake_table",
            catalog_id=None,
            position=Position3D(x_m=center, y_m=0.45, z_m=0),
            dimensions=table_dimensions,
        )
        cake_width = request.cake.diameter_m or request.cake.width_m or 0.3
        cake_depth = request.cake.diameter_m or request.cake.depth_m or cake_width
        cake_dimensions = Dimensions(
            width_m=cake_width,
            depth_m=cake_depth,
            height_m=request.cake.height_m,
        )
        cake_object = ObjectPlacement(
            asset_id=cake_row["ar_asset_key"],
            role="cake",
            catalog_id=cake_row["cake_design_id"],
            position=Position3D(x_m=center, y_m=0.45, z_m=table_dimensions.height_m),
            dimensions=cake_dimensions,
        )
        per_serving = 450 if "premium" in cake_row["price_tier"] else 350
        estimated_cost = (
            request.cake.servings_required * per_serving + request.cake.tiers * 1_500
        )
        cake = CakePlacement(
            catalog_id=cake_row["cake_design_id"],
            source_image_reference=request.cake.cake_image_reference,
            shape=request.cake.shape,
            tiers=request.cake.tiers,
            placement=cake_object,
            servings=request.cake.servings_required,
            estimated_cost_pkr=estimated_cost,
        )
        return cake, [table, cake_object], estimated_cost

    def _place_decor(
        self,
        request: DesignRequest,
        selected: list[tuple[dict[str, str], int, int]],
        center: float,
        table_dimensions: Dimensions,
    ) -> tuple[list[DecorRecommendation], list[ObjectPlacement], int]:
        recommendations: list[DecorRecommendation] = []
        objects: list[ObjectPlacement] = []
        total = 0
        for row, quantity, unit_cost in selected:
            placements = [
                self._decor_placement(
                    request,
                    row,
                    index,
                    quantity,
                    center,
                    table_dimensions,
                )
                for index in range(quantity)
            ]
            recommendations.append(
                DecorRecommendation(
                    catalog_id=row["decor_id"],
                    name=row["item_name"],
                    category=row["category"],
                    quantity=quantity,
                    unit_cost_pkr=unit_cost,
                    placements=placements,
                )
            )
            objects.extend(placements)
            total += quantity * unit_cost
        return recommendations, objects, total

    @staticmethod
    def _decor_placement(
        request: DesignRequest,
        row: dict[str, str],
        index: int,
        quantity: int,
        center: float,
        table_dimensions: Dimensions,
    ) -> ObjectPlacement:
        category = row["category"]
        space_width = request.space.dimensions.width_m
        if category == "backdrop":
            role = "backdrop"
            position = Position3D(x_m=center, y_m=0.05, z_m=0)
            dimensions = Dimensions(
                width_m=min(2.2, max(0.01, space_width - 0.01)),
                depth_m=0.2,
                height_m=min(2.2, request.space.dimensions.height_m),
            )
        elif category == "floor-arrangement":
            role = "decoration"
            if index == 0:
                offset = -table_dimensions.width_m / 2 - 0.25
            else:
                offset = table_dimensions.width_m / 2 + 0.25
            x_position = min(max(center + offset, 0), space_width)
            position = Position3D(x_m=x_position, y_m=0.55, z_m=0)
            dimensions = Dimensions(width_m=0.4, depth_m=0.4, height_m=0.8)
        elif category == "lighting":
            role = "lighting"
            spread = (index - (quantity - 1) / 2) * min(
                0.7, space_width / max(quantity, 1)
            )
            position = Position3D(
                x_m=min(max(center + spread, 0), space_width),
                y_m=0.1,
                z_m=max(0.1, request.space.dimensions.height_m - 0.3),
            )
            dimensions = Dimensions(width_m=0.2, depth_m=0.2, height_m=0.3)
        elif category == "signage":
            role = "signage"
            position = Position3D(
                x_m=min(
                    max(center - table_dimensions.width_m / 2 - 0.35, 0),
                    space_width,
                ),
                y_m=0.5,
                z_m=0,
            )
            dimensions = Dimensions(width_m=0.4, depth_m=0.3, height_m=1.2)
        else:
            role = "decoration"
            position = Position3D(
                x_m=center,
                y_m=0.45,
                z_m=table_dimensions.height_m,
            )
            dimensions = Dimensions(width_m=0.6, depth_m=0.3, height_m=0.1)
        return ObjectPlacement(
            asset_id=row["ar_asset_key"],
            role=role,
            catalog_id=row["decor_id"],
            position=position,
            dimensions=dimensions,
        )
