from app.schemas.design import DesignRequest, Dimensions, ObjectPlacement, Position3D
from app.schemas.professional import RoomConstraintRequest
from app.services.room_constraints import RoomConstraintEngine


def _space(*, width=4.0, depth=4.0, height=2.8, confirmed=True, obstacles=None):
    return {
        "area_type": "room",
        "venue_type": "living_room",
        "environment": "indoor",
        "dimensions": {
            "width_m": width,
            "depth_m": depth,
            "height_m": height,
        },
        "obstacles": obstacles or [],
        "obstacle_map_confirmed": confirmed,
        "photo_references": [],
        "photo_evidence": [],
    }


def test_clean_confirmed_room_has_verified_focal_zone():
    request = RoomConstraintRequest.model_validate(
        {
            "space": _space(),
            "minimum_clearance_m": 0.9,
            "objects": [],
        }
    )

    result = RoomConstraintEngine().assess(request)

    assert result.status == "verified"
    assert result.hard_constraints_ready is True
    assert result.largest_focal_zone is not None
    assert result.scale_targets is not None
    assert result.scale_targets.recommended_backdrop_width_m > 2.0
    assert result.available_front_clearance_m == 4.0


def test_unconfirmed_obstacle_map_requires_manual_review():
    request = RoomConstraintRequest.model_validate(
        {
            "space": _space(confirmed=False),
            "minimum_clearance_m": 0.9,
        }
    )

    result = RoomConstraintEngine().assess(request)

    assert result.status == "manual_review_required"
    assert result.hard_constraints_ready is False


def test_door_reduces_the_usable_focal_span():
    clean = RoomConstraintEngine().assess(
        RoomConstraintRequest.model_validate(
            {"space": _space(), "minimum_clearance_m": 0.9}
        )
    )
    with_door = RoomConstraintEngine().assess(
        RoomConstraintRequest.model_validate(
            {
                "space": _space(
                    obstacles=[
                        {
                            "obstacle_type": "door",
                            "label": "main door",
                            "position": {"x_m": 1.5, "y_m": 0.0, "z_m": 0.0},
                            "dimensions": {
                                "width_m": 1.0,
                                "depth_m": 0.1,
                                "height_m": 2.1,
                            },
                        }
                    ]
                ),
                "minimum_clearance_m": 0.9,
            }
        )
    )

    assert clean.largest_focal_zone is not None
    assert with_door.largest_focal_zone is not None
    assert with_door.largest_focal_zone.width_m < clean.largest_focal_zone.width_m


def test_large_room_gets_a_larger_visual_target_than_small_room():
    engine = RoomConstraintEngine()
    small = engine.assess(
        RoomConstraintRequest.model_validate(
            {"space": _space(width=4.0, depth=4.0), "minimum_clearance_m": 0.9}
        )
    )
    large = engine.assess(
        RoomConstraintRequest.model_validate(
            {"space": _space(width=10.0, depth=6.0, height=3.2), "minimum_clearance_m": 0.9}
        )
    )

    assert small.scale_targets is not None
    assert large.scale_targets is not None
    assert large.scale_targets.size_class == "large"
    assert (
        large.scale_targets.recommended_backdrop_width_m
        > small.scale_targets.recommended_backdrop_width_m
    )


def test_measured_furniture_collision_is_rejected():
    request = RoomConstraintRequest.model_validate(
        {
            "space": _space(
                obstacles=[
                    {
                        "obstacle_type": "furniture",
                        "label": "sofa",
                        "position": {"x_m": 1.0, "y_m": 1.0, "z_m": 0.0},
                        "dimensions": {
                            "width_m": 1.0,
                            "depth_m": 1.0,
                            "height_m": 0.9,
                        },
                    }
                ]
            ),
            "minimum_clearance_m": 0.9,
            "objects": [
                {
                    "asset_id": "test-floor-decor",
                    "role": "decoration",
                    "position": {"x_m": 1.5, "y_m": 1.5, "z_m": 0.0},
                    "dimensions": {
                        "width_m": 0.5,
                        "depth_m": 0.5,
                        "height_m": 0.8,
                    },
                }
            ],
        }
    )

    result = RoomConstraintEngine().assess(request)

    assert result.status == "violations"
    assert result.hard_constraints_ready is False
    assert any(item.code == "obstacle_collision" for item in result.violations)


def test_shallow_room_detects_insufficient_circulation():
    request = RoomConstraintRequest.model_validate(
        {
            "space": _space(width=4.0, depth=2.0),
            "minimum_clearance_m": 0.9,
            "objects": [
                {
                    "asset_id": "wide-table",
                    "role": "cake_table",
                    "position": {"x_m": 2.0, "y_m": 1.0, "z_m": 0.0},
                    "dimensions": {
                        "width_m": 1.5,
                        "depth_m": 1.0,
                        "height_m": 0.9,
                    },
                }
            ],
        }
    )

    result = RoomConstraintEngine().assess(request)

    assert result.status == "violations"
    assert any(
        item.code == "insufficient_circulation"
        for item in result.violations
    )


def test_large_verified_room_expands_only_the_procedural_planning_envelope(
    valid_design_request,
):
    payload = valid_design_request
    payload["space"]["dimensions"] = {
        "width_m": 10.0,
        "depth_m": 6.0,
        "height_m": 3.2,
    }
    request = DesignRequest.model_validate(payload)
    objects = [
        ObjectPlacement(
            asset_id="real-catalog/backdrop-round-arch",
            role="backdrop",
            catalog_id="backdrop-round-arch",
            position=Position3D(x_m=5.0, y_m=0.3, z_m=0.0),
            dimensions=Dimensions(width_m=2.0, depth_m=0.55, height_m=2.2),
        ),
        ObjectPlacement(
            asset_id="builtin/cake-table",
            role="cake_table",
            position=Position3D(x_m=5.0, y_m=0.8, z_m=0.0),
            dimensions=Dimensions(width_m=1.5, depth_m=0.75, height_m=0.9),
        ),
        ObjectPlacement(
            asset_id="cake-model",
            role="cake",
            position=Position3D(x_m=5.0, y_m=0.8, z_m=0.9),
            dimensions=Dimensions(width_m=0.3, depth_m=0.3, height_m=0.35),
        ),
    ]

    fit = RoomConstraintEngine().fit_scene(request, objects)

    assert fit.assessment.hard_constraints_ready is True
    backdrop = next(item for item in fit.objects if item.role == "backdrop")
    table = next(item for item in fit.objects if item.role == "cake_table")
    cake = next(item for item in fit.objects if item.role == "cake")
    assert backdrop.dimensions is not None
    assert backdrop.dimensions.width_m > 5.0
    assert table.dimensions is not None
    assert table.dimensions.width_m > 1.5
    assert cake.dimensions is not None
    assert cake.dimensions.width_m == 0.3
    assert cake.position.x_m == table.position.x_m
    assert cake.position.y_m == table.position.y_m
