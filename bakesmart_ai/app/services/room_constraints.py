"""Deterministic metre-based room constraints and scale-aware scene fitting."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.design import DesignRequest, Dimensions, ObjectPlacement, Position3D
from app.schemas.professional import (
    ConstraintViolation,
    ConstraintZone,
    MetricRect2D,
    RoomConstraintRequest,
    RoomConstraintResponse,
    ScaleAwareTargets,
)


MIN_USABLE_FOCAL_WIDTH_M = 0.75
FLOOR_BLOCKERS = {"door", "furniture", "stairs", "walkway", "other"}
WALL_BLOCKERS = {"door", "window", "outlet", "furniture", "stairs", "walkway", "other"}


@dataclass(frozen=True)
class _AABB:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def overlaps(self, other: "_AABB") -> bool:
        return (
            self.min_x < other.max_x
            and self.max_x > other.min_x
            and self.min_y < other.max_y
            and self.max_y > other.min_y
            and self.min_z < other.max_z
            and self.max_z > other.min_z
        )


@dataclass(frozen=True)
class SceneFitResult:
    objects: tuple[ObjectPlacement, ...]
    assessment: RoomConstraintResponse
    warnings: tuple[str, ...]


class RoomConstraintEngine:
    """Apply hard geometry rules without estimating any physical measurement."""

    _limitations = [
        "Coordinates come only from customer-entered measurements; BakeSmart does not infer metres from photo appearance.",
        "Collision checks currently use axis-aligned boxes; rotated-object OBB collision is not implemented yet.",
        "Door hinge and swing direction are not present in the current input schema, so only the measured door footprint plus clearance is protected.",
        "Scale targets describe a planning composition envelope. Real production assets must keep their true dimensions and use larger or repeated modular pieces instead of texture stretching.",
        "Photo perspective projection is a separate calibrated-plane step and is not solved by this room endpoint.",
    ]

    def assess(self, request: RoomConstraintRequest) -> RoomConstraintResponse:
        space = request.space
        width = space.dimensions.width_m
        depth = space.dimensions.depth_m
        room_bounds = MetricRect2D(
            x_m=0,
            y_m=0,
            width_m=width,
            depth_m=depth or 0,
        )
        focal_zone = self._largest_focal_zone(
            space=space,
            minimum_clearance_m=request.minimum_clearance_m,
        )
        targets = (
            self._scale_targets(space, focal_zone)
            if focal_zone is not None
            else None
        )
        forbidden_zones = self._forbidden_zones(
            space=space,
            minimum_clearance_m=request.minimum_clearance_m,
        )
        violations: list[ConstraintViolation] = []
        if depth is None:
            violations.append(
                ConstraintViolation(
                    code="missing_dimensions",
                    message=(
                        "Room depth is required before BakeSmart can verify floor "
                        "collisions and the circulation route."
                    ),
                )
            )
            available_clearance = 0.0
        else:
            violations.extend(
                self._validate_objects(
                    space=space,
                    objects=request.objects,
                    minimum_clearance_m=request.minimum_clearance_m,
                )
            )
            available_clearance = self._available_front_clearance(
                depth=depth,
                objects=request.objects,
            )
            if request.objects and available_clearance < request.minimum_clearance_m:
                violations.append(
                    ConstraintViolation(
                        code="insufficient_circulation",
                        message=(
                            f"The fitted setup leaves {available_clearance:.3f} m "
                            f"in front, below the required "
                            f"{request.minimum_clearance_m:.3f} m circulation."
                        ),
                    )
                )

        if focal_zone is None:
            status = "no_usable_zone"
        elif violations:
            status = "violations"
        elif not space.obstacle_map_confirmed:
            status = "manual_review_required"
        else:
            status = "verified"
        hard_ready = (
            status == "verified"
            and depth is not None
            and space.obstacle_map_confirmed
        )
        limitations = list(self._limitations)
        if not space.obstacle_map_confirmed:
            limitations.insert(
                0,
                "The obstacle map is not customer-confirmed, so this geometry must remain a manual-review result.",
            )
        return RoomConstraintResponse(
            status=status,
            room_bounds=room_bounds,
            largest_focal_zone=focal_zone,
            forbidden_zones=forbidden_zones,
            scale_targets=targets,
            hard_constraints_ready=hard_ready,
            available_front_clearance_m=round(available_clearance, 6),
            violations=self._deduplicate_violations(violations),
            limitations=limitations,
        )

    def fit_scene(
        self,
        request: DesignRequest,
        objects: list[ObjectPlacement],
    ) -> SceneFitResult:
        """Fit a procedural planning scene into the largest verified focal span."""

        empty_assessment = self.assess(
            RoomConstraintRequest(
                space=request.space,
                minimum_clearance_m=request.minimum_clearance_m,
                objects=[],
            )
        )
        zone = empty_assessment.largest_focal_zone
        targets = empty_assessment.scale_targets
        if zone is None or targets is None:
            return SceneFitResult(
                objects=tuple(objects),
                assessment=empty_assessment,
                warnings=(
                    "No usable focal span was available, so the existing scene placement was left unchanged.",
                ),
            )

        focal_center = zone.x_m + zone.width_m / 2
        fitted = list(objects)
        warnings: list[str] = []

        backdrop_indexes = [
            index for index, item in enumerate(fitted) if item.role == "backdrop"
        ]
        for index in backdrop_indexes:
            item = fitted[index]
            dimensions = item.dimensions
            if dimensions is None:
                continue
            target_width = targets.recommended_backdrop_width_m
            target_height = targets.recommended_backdrop_height_m
            expanded_width = max(dimensions.width_m, target_width)
            expanded_height = max(dimensions.height_m, target_height)
            new_dimensions = Dimensions(
                width_m=expanded_width,
                depth_m=dimensions.depth_m,
                height_m=expanded_height,
            )
            depth_m = dimensions.depth_m or 0.2
            fitted[index] = item.model_copy(
                update={
                    "position": item.position.model_copy(
                        update={
                            "x_m": focal_center,
                            "y_m": max(depth_m / 2, 0.05),
                        }
                    ),
                    "dimensions": new_dimensions,
                }
            )
            if (
                expanded_width > dimensions.width_m + 0.05
                or expanded_height > dimensions.height_m + 0.05
            ):
                warnings.append(
                    "The procedural backdrop was expanded to the room's scale-aware planning envelope. Production must use a larger or modular repeated setup at true dimensions; do not stretch one catalogue asset."
                )

        backdrop_front = 0.0
        for index in backdrop_indexes:
            item = fitted[index]
            if item.dimensions is None:
                continue
            backdrop_front = max(
                backdrop_front,
                item.position.y_m + (item.dimensions.depth_m or 0.0) / 2,
            )

        table_indexes = [
            index for index, item in enumerate(fitted) if item.role == "cake_table"
        ]
        cake_width = request.cake.diameter_m or request.cake.width_m or 0.3
        fitted_table_width = max(
            targets.recommended_table_width_m,
            cake_width + 0.5,
        )
        fitted_table_width = min(fitted_table_width, zone.width_m)
        for index in table_indexes:
            item = fitted[index]
            dimensions = item.dimensions or Dimensions(
                width_m=fitted_table_width,
                depth_m=0.75,
                height_m=0.9,
            )
            table_depth = dimensions.depth_m or 0.75
            table_y = max(
                table_depth / 2 + 0.05,
                backdrop_front + 0.05 + table_depth / 2,
            )
            new_dimensions = Dimensions(
                width_m=max(dimensions.width_m, fitted_table_width),
                depth_m=table_depth,
                height_m=dimensions.height_m,
            )
            fitted[index] = item.model_copy(
                update={
                    "position": item.position.model_copy(
                        update={"x_m": focal_center, "y_m": table_y}
                    ),
                    "dimensions": new_dimensions,
                }
            )
            if new_dimensions.width_m > dimensions.width_m + 0.05:
                warnings.append(
                    "The built-in cake table planning geometry was widened to match the usable focal span and cake size."
                )

        primary_table = fitted[table_indexes[0]] if table_indexes else None
        if primary_table is not None and primary_table.dimensions is not None:
            pass

        for index, item in enumerate(fitted):
            if item.role != "cake" or primary_table is None:
                continue
            table_height = (
                primary_table.dimensions.height_m
                if primary_table.dimensions is not None
                else item.position.z_m
            )
            fitted[index] = item.model_copy(
                update={
                    "position": Position3D(
                        x_m=primary_table.position.x_m,
                        y_m=primary_table.position.y_m,
                        z_m=table_height,
                    )
                }
            )

        floor_indexes = [
            index
            for index, item in enumerate(fitted)
            if item.role == "decoration"
            and item.position.z_m < 0.05
            and (
                "floor-arrangement" in item.asset_id.lower()
                or (item.catalog_id or "").startswith("floor-")
            )
        ]
        if floor_indexes:
            self._fit_floor_decor(
                fitted=fitted,
                indexes=floor_indexes,
                zone=zone,
                focal_center=focal_center,
                table=primary_table,
                backdrop_front=backdrop_front,
            )

        signage_indexes = [
            index
            for index, item in enumerate(fitted)
            if item.role == "signage" and item.position.z_m < 0.05
        ]
        for order, index in enumerate(signage_indexes):
            item = fitted[index]
            if item.dimensions is None:
                continue
            half_width = item.dimensions.width_m / 2
            side_x = (
                zone.x_m + half_width
                if order % 2 == 0
                else zone.x_m + zone.width_m - half_width
            )
            depth_m = item.dimensions.depth_m or 0.1
            fitted[index] = item.model_copy(
                update={
                    "position": item.position.model_copy(
                        update={
                            "x_m": self._clamp_center(
                                side_x,
                                half_width,
                                zone.x_m,
                                zone.x_m + zone.width_m,
                            ),
                            "y_m": max(depth_m / 2 + 0.05, backdrop_front),
                        }
                    )
                }
            )

        lighting_indexes = [
            index for index, item in enumerate(fitted) if item.role == "lighting"
        ]
        if lighting_indexes:
            for order, index in enumerate(lighting_indexes):
                item = fitted[index]
                if item.dimensions is None:
                    continue
                half_width = item.dimensions.width_m / 2
                if len(lighting_indexes) == 1:
                    x_m = focal_center
                else:
                    ratio = order / (len(lighting_indexes) - 1)
                    x_m = zone.x_m + half_width + ratio * max(
                        0.0,
                        zone.width_m - 2 * half_width,
                    )
                depth_m = item.dimensions.depth_m or 0.1
                fitted[index] = item.model_copy(
                    update={
                        "position": item.position.model_copy(
                            update={
                                "x_m": self._clamp_center(
                                    x_m,
                                    half_width,
                                    zone.x_m,
                                    zone.x_m + zone.width_m,
                                ),
                                "y_m": max(depth_m / 2, 0.05),
                            }
                        )
                    }
                )

        assessment = self.assess(
            RoomConstraintRequest(
                space=request.space,
                minimum_clearance_m=request.minimum_clearance_m,
                objects=fitted,
            )
        )
        if assessment.hard_constraints_ready:
            warnings.append(
                "Scale-aware scene fitting passed the confirmed room bounds, obstacle AABBs, object AABBs, and minimum circulation check."
            )
        else:
            warnings.append(
                "The scale-aware fitted candidate did not pass every hard constraint, so callers must keep the previous placement or request manual correction."
            )
        return SceneFitResult(
            objects=tuple(fitted),
            assessment=assessment,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _fit_floor_decor(
        self,
        *,
        fitted: list[ObjectPlacement],
        indexes: list[int],
        zone: MetricRect2D,
        focal_center: float,
        table: ObjectPlacement | None,
        backdrop_front: float,
    ) -> None:
        table_width = (
            table.dimensions.width_m
            if table is not None and table.dimensions is not None
            else 0.0
        )
        table_y = table.position.y_m if table is not None else backdrop_front + 0.5
        table_depth = (
            (table.dimensions.depth_m or 0.75)
            if table is not None and table.dimensions is not None
            else 0.75
        )
        left_cursor = focal_center - table_width / 2 - 0.12
        right_cursor = focal_center + table_width / 2 + 0.12
        for order, index in enumerate(indexes):
            item = fitted[index]
            if item.dimensions is None:
                continue
            width = item.dimensions.width_m
            depth = item.dimensions.depth_m or 0.4
            half_width = width / 2
            if order % 2 == 0:
                x_m = left_cursor - half_width
                left_cursor = x_m - half_width - 0.12
            else:
                x_m = right_cursor + half_width
                right_cursor = x_m + half_width + 0.12
            x_m = self._clamp_center(
                x_m,
                half_width,
                zone.x_m,
                zone.x_m + zone.width_m,
            )
            y_m = max(
                depth / 2 + 0.05,
                backdrop_front + 0.05 + depth / 2,
                table_y + min(table_depth, depth) * 0.05,
            )
            fitted[index] = item.model_copy(
                update={
                    "position": item.position.model_copy(
                        update={"x_m": x_m, "y_m": y_m}
                    )
                }
            )

    def _largest_focal_zone(
        self,
        *,
        space,
        minimum_clearance_m: float,
    ) -> MetricRect2D | None:
        width = space.dimensions.width_m
        depth = space.dimensions.depth_m or 0.0
        side_margin = max(
            0.1,
            min(minimum_clearance_m * 0.2, width * 0.06),
        )
        start = side_margin
        end = width - side_margin
        if end - start < MIN_USABLE_FOCAL_WIDTH_M:
            return None

        blocked: list[tuple[float, float]] = []
        for obstacle in space.obstacles:
            obstacle_type = obstacle.obstacle_type.value
            if obstacle_type not in WALL_BLOCKERS:
                continue
            obstacle_depth = obstacle.dimensions.depth_m or 0.0
            front_reach = obstacle.position.y_m + obstacle_depth
            if obstacle_type in {"furniture", "stairs", "walkway", "other"}:
                if front_reach > 1.5 + minimum_clearance_m * 0.25:
                    continue
            elif obstacle.position.y_m > max(0.45, obstacle_depth + 0.15):
                continue
            buffer_m = self._wall_buffer(obstacle_type, minimum_clearance_m)
            left = max(start, obstacle.position.x_m - buffer_m)
            right = min(
                end,
                obstacle.position.x_m + obstacle.dimensions.width_m + buffer_m,
            )
            if right > left:
                blocked.append((left, right))

        merged = self._merge_intervals(blocked)
        gaps: list[tuple[float, float]] = []
        cursor = start
        for left, right in merged:
            if left > cursor:
                gaps.append((cursor, left))
            cursor = max(cursor, right)
        if cursor < end:
            gaps.append((cursor, end))
        if not gaps:
            return None
        left, right = max(gaps, key=lambda pair: pair[1] - pair[0])
        if right - left < MIN_USABLE_FOCAL_WIDTH_M:
            return None
        return MetricRect2D(
            x_m=round(left, 6),
            y_m=0,
            width_m=round(right - left, 6),
            depth_m=round(min(depth, 1.8), 6),
        )

    def _forbidden_zones(
        self,
        *,
        space,
        minimum_clearance_m: float,
    ) -> list[ConstraintZone]:
        width = space.dimensions.width_m
        depth = space.dimensions.depth_m or 0.0
        if depth <= 0:
            return []
        zones: list[ConstraintZone] = []
        for obstacle in space.obstacles:
            obstacle_type = obstacle.obstacle_type.value
            obstacle_depth = obstacle.dimensions.depth_m or 0.0
            clearance = (
                minimum_clearance_m
                if obstacle_type in FLOOR_BLOCKERS
                else min(0.2, minimum_clearance_m * 0.25)
            )
            x0 = max(0.0, obstacle.position.x_m - clearance)
            x1 = min(
                width,
                obstacle.position.x_m + obstacle.dimensions.width_m + clearance,
            )
            y0 = max(0.0, obstacle.position.y_m - clearance)
            y1 = min(depth, obstacle.position.y_m + obstacle_depth + clearance)
            if x1 <= x0 or y1 <= y0:
                continue
            zones.append(
                ConstraintZone(
                    label=obstacle.label,
                    source_type=obstacle_type,
                    bounds=MetricRect2D(
                        x_m=round(x0, 6),
                        y_m=round(y0, 6),
                        width_m=round(x1 - x0, 6),
                        depth_m=round(y1 - y0, 6),
                    ),
                    clearance_m=round(clearance, 6),
                )
            )
        return zones

    def _validate_objects(
        self,
        *,
        space,
        objects: list[ObjectPlacement],
        minimum_clearance_m: float,
    ) -> list[ConstraintViolation]:
        depth = space.dimensions.depth_m
        if depth is None:
            return []
        room_width = space.dimensions.width_m
        room_height = space.dimensions.height_m
        violations: list[ConstraintViolation] = []
        object_boxes: list[tuple[ObjectPlacement, _AABB]] = []
        for item in objects:
            if item.dimensions is None:
                violations.append(
                    ConstraintViolation(
                        code="missing_dimensions",
                        asset_id=item.asset_id,
                        message=(
                            f"'{item.asset_id}' has no physical dimensions, so its "
                            "room fit cannot be verified."
                        ),
                    )
                )
                continue
            box = self._object_box(item)
            object_boxes.append((item, box))
            if (
                box.min_x < -1e-6
                or box.min_y < -1e-6
                or box.min_z < -1e-6
                or box.max_x > room_width + 1e-6
                or box.max_y > depth + 1e-6
                or box.max_z > room_height + 1e-6
            ):
                violations.append(
                    ConstraintViolation(
                        code="out_of_room",
                        asset_id=item.asset_id,
                        message=(
                            f"'{item.asset_id}' extends outside the measured "
                            "room bounds."
                        ),
                    )
                )

            for obstacle in space.obstacles:
                obstacle_box = self._protected_obstacle_box(
                    obstacle=obstacle,
                    room_width=room_width,
                    room_depth=depth,
                    room_height=room_height,
                    minimum_clearance_m=minimum_clearance_m,
                )
                if not box.overlaps(obstacle_box):
                    continue
                violations.append(
                    ConstraintViolation(
                        code="obstacle_collision",
                        asset_id=item.asset_id,
                        message=(
                            f"'{item.asset_id}' enters the protected clearance "
                            f"around the measured {obstacle.obstacle_type.value} "
                            f"'{obstacle.label}'."
                        ),
                    )
                )

        for first_index, (first, first_box) in enumerate(object_boxes):
            for second, second_box in object_boxes[first_index + 1 :]:
                if not self._requires_object_separation(first, second):
                    continue
                if first_box.overlaps(second_box):
                    violations.append(
                        ConstraintViolation(
                            code="object_collision",
                            asset_id=first.asset_id,
                            message=(
                                f"'{first.asset_id}' overlaps '{second.asset_id}' "
                                "in the fitted axis-aligned scene."
                            ),
                        )
                    )
        return violations

    @staticmethod
    def _requires_object_separation(
        first: ObjectPlacement,
        second: ObjectPlacement,
    ) -> bool:
        if "lighting" in {first.role, second.role}:
            return False
        if {first.role, second.role} == {"backdrop", "signage"}:
            return False
        return True

    @staticmethod
    def _object_box(item: ObjectPlacement) -> _AABB:
        assert item.dimensions is not None
        depth = item.dimensions.depth_m or 0.01
        return _AABB(
            min_x=item.position.x_m - item.dimensions.width_m / 2,
            min_y=item.position.y_m - depth / 2,
            min_z=item.position.z_m,
            max_x=item.position.x_m + item.dimensions.width_m / 2,
            max_y=item.position.y_m + depth / 2,
            max_z=item.position.z_m + item.dimensions.height_m,
        )

    @staticmethod
    def _protected_obstacle_box(
        *,
        obstacle,
        room_width: float,
        room_depth: float,
        room_height: float,
        minimum_clearance_m: float,
    ) -> _AABB:
        obstacle_type = obstacle.obstacle_type.value
        if obstacle_type in FLOOR_BLOCKERS:
            lateral = (
                minimum_clearance_m * 0.5
                if obstacle_type in {"door", "stairs", "walkway"}
                else min(0.35, minimum_clearance_m * 0.4)
            )
            front_back = minimum_clearance_m
        elif obstacle_type == "window":
            lateral = front_back = 0.12
        elif obstacle_type == "outlet":
            lateral = front_back = 0.15
        else:
            lateral = front_back = min(0.25, minimum_clearance_m * 0.3)
        raw = RoomConstraintEngine._obstacle_box(obstacle)
        return _AABB(
            min_x=max(0.0, raw.min_x - lateral),
            min_y=max(0.0, raw.min_y - front_back),
            min_z=max(0.0, raw.min_z),
            max_x=min(room_width, raw.max_x + lateral),
            max_y=min(room_depth, raw.max_y + front_back),
            max_z=min(room_height, raw.max_z),
        )

    @staticmethod
    def _obstacle_box(obstacle) -> _AABB:
        depth = obstacle.dimensions.depth_m or 0.01
        return _AABB(
            min_x=obstacle.position.x_m,
            min_y=obstacle.position.y_m,
            min_z=obstacle.position.z_m,
            max_x=obstacle.position.x_m + obstacle.dimensions.width_m,
            max_y=obstacle.position.y_m + depth,
            max_z=obstacle.position.z_m + obstacle.dimensions.height_m,
        )

    @staticmethod
    def _available_front_clearance(
        *,
        depth: float,
        objects: list[ObjectPlacement],
    ) -> float:
        setup_front = 0.0
        for item in objects:
            if item.dimensions is None or item.role == "lighting":
                continue
            if item.position.z_m > 0.05 and item.role not in {"backdrop", "signage"}:
                continue
            object_depth = item.dimensions.depth_m or 0.0
            setup_front = max(
                setup_front,
                item.position.y_m + object_depth / 2,
            )
        return max(0.0, depth - setup_front)

    @staticmethod
    def _scale_targets(space, zone: MetricRect2D) -> ScaleAwareTargets:
        usable = zone.width_m
        if usable < 3.5:
            size_class = "compact"
            coverage = 0.80
        elif usable < 6:
            size_class = "standard"
            coverage = 0.78
        elif usable < 10:
            size_class = "large"
            coverage = 0.76
        else:
            size_class = "hall"
            coverage = 0.74
        backdrop_width = min(usable, max(min(1.4, usable), usable * coverage))
        backdrop_height = min(
            space.dimensions.height_m * 0.88,
            max(1.8, backdrop_width * 0.5),
        )
        table_limit = min(3.0, usable * 0.65)
        table_width = min(
            table_limit,
            max(min(1.4, table_limit), backdrop_width * 0.42),
        )
        floor_spread = min(
            usable * 0.92,
            max(table_width + 0.8, backdrop_width * 0.78),
        )
        return ScaleAwareTargets(
            size_class=size_class,
            usable_focal_width_m=round(usable, 6),
            recommended_backdrop_width_m=round(backdrop_width, 6),
            recommended_backdrop_height_m=round(backdrop_height, 6),
            recommended_table_width_m=round(table_width, 6),
            recommended_floor_decor_spread_m=round(floor_spread, 6),
            backdrop_wall_coverage_fraction=round(
                backdrop_width / usable,
                6,
            ),
        )

    @staticmethod
    def _wall_buffer(obstacle_type: str, minimum_clearance_m: float) -> float:
        if obstacle_type in {"door", "stairs", "walkway"}:
            return minimum_clearance_m * 0.5
        if obstacle_type == "furniture":
            return min(0.35, minimum_clearance_m * 0.4)
        if obstacle_type == "outlet":
            return 0.15
        if obstacle_type == "window":
            return 0.12
        return min(0.25, minimum_clearance_m * 0.3)

    @staticmethod
    def _merge_intervals(
        intervals: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        if not intervals:
            return []
        merged: list[list[float]] = []
        for left, right in sorted(intervals):
            if not merged or left > merged[-1][1]:
                merged.append([left, right])
            else:
                merged[-1][1] = max(merged[-1][1], right)
        return [(left, right) for left, right in merged]

    @staticmethod
    def _clamp_center(
        center: float,
        half_width: float,
        left: float,
        right: float,
    ) -> float:
        low = left + half_width
        high = right - half_width
        if low > high:
            return (left + right) / 2
        return min(max(center, low), high)

    @staticmethod
    def _deduplicate_violations(
        violations: list[ConstraintViolation],
    ) -> list[ConstraintViolation]:
        output: list[ConstraintViolation] = []
        seen: set[tuple[str, str | None, str]] = set()
        for violation in violations:
            key = (violation.code, violation.asset_id, violation.message)
            if key in seen:
                continue
            seen.add(key)
            output.append(violation)
        return output


room_constraint_engine = RoomConstraintEngine()
