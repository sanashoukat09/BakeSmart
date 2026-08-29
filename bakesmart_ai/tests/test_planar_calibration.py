from app.schemas.professional import (
    PlanarCalibrationRequest,
    PlanarProjectionRequest,
)
from app.services.calibration import CalibrationService


def _wall_payload(*, all_confirmed: bool = True):
    confirmations = [True, True, True, all_confirmed]
    return {
        "photo_id": "venue-photo-0123456789abcdef0123",
        "image_width_px": 1000,
        "image_height_px": 600,
        "plane_type": "wall",
        "anchors": [
            {
                "label": "bottom-left",
                "image": {"x_fraction": 0.10, "y_fraction": 0.85},
                "plane": {"x_m": 0.0, "y_m": 0.0},
                "customer_confirmed": confirmations[0],
            },
            {
                "label": "bottom-right",
                "image": {"x_fraction": 0.80, "y_fraction": 0.80},
                "plane": {"x_m": 2.0, "y_m": 0.0},
                "customer_confirmed": confirmations[1],
            },
            {
                "label": "top-right",
                "image": {"x_fraction": 0.75, "y_fraction": 0.20},
                "plane": {"x_m": 2.0, "y_m": 1.5},
                "customer_confirmed": confirmations[2],
            },
            {
                "label": "top-left",
                "image": {"x_fraction": 0.15, "y_fraction": 0.20},
                "plane": {"x_m": 0.0, "y_m": 1.5},
                "customer_confirmed": confirmations[3],
            },
        ],
    }


def test_four_confirmed_points_solve_one_physical_plane():
    request = PlanarCalibrationRequest.model_validate(_wall_payload())
    result = CalibrationService().calibrate_plane(request)

    assert result.status == "calibrated"
    assert result.planar_projection_ready is True
    assert result.full_camera_calibration_ready is False
    assert result.anchors_used == 4
    assert result.confirmed_anchor_count == 4
    assert result.homography_m_to_px is not None
    assert result.homography_px_to_m is not None
    assert result.rms_reprojection_error_px is not None
    assert result.rms_reprojection_error_px < 1e-5
    assert result.fit_quality == "medium"
    assert any("Exactly four anchors" in item for item in result.limitations)


def test_unconfirmed_anchor_blocks_metric_plane_solution():
    request = PlanarCalibrationRequest.model_validate(
        _wall_payload(all_confirmed=False)
    )
    result = CalibrationService().calibrate_plane(request)

    assert result.status == "needs_customer_confirmation"
    assert result.planar_projection_ready is False
    assert result.homography_m_to_px is None
    assert result.confirmed_anchor_count == 3


def test_collinear_metric_points_are_rejected():
    payload = _wall_payload()
    for index, anchor in enumerate(payload["anchors"]):
        anchor["plane"] = {"x_m": float(index), "y_m": 0.0}
    request = PlanarCalibrationRequest.model_validate(payload)
    result = CalibrationService().calibrate_plane(request)

    assert result.status == "invalid_geometry"
    assert result.planar_projection_ready is False
    assert result.homography_m_to_px is None


def test_metric_point_projects_back_into_photo_plane():
    calibration = PlanarCalibrationRequest.model_validate(_wall_payload())
    request = PlanarProjectionRequest.model_validate(
        {
            "calibration": calibration.model_dump(mode="json"),
            "points_m": [
                {"x_m": 1.0, "y_m": 0.75},
                {"x_m": 1.0, "y_m": 3.0},
            ],
        }
    )
    result = CalibrationService().project_plane_points(request)

    assert result.calibration.status == "calibrated"
    assert len(result.projected_points) == 2
    assert result.projected_points[0].inside_image is True
    assert 0 < result.projected_points[0].x_fraction < 1
    assert 0 < result.projected_points[0].y_fraction < 1
    assert result.projected_points[1].inside_image is False
