def _plane_payload():
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
                "customer_confirmed": True,
            },
            {
                "label": "bottom-right",
                "image": {"x_fraction": 0.80, "y_fraction": 0.80},
                "plane": {"x_m": 2.0, "y_m": 0.0},
                "customer_confirmed": True,
            },
            {
                "label": "top-right",
                "image": {"x_fraction": 0.75, "y_fraction": 0.20},
                "plane": {"x_m": 2.0, "y_m": 1.5},
                "customer_confirmed": True,
            },
            {
                "label": "top-left",
                "image": {"x_fraction": 0.15, "y_fraction": 0.20},
                "plane": {"x_m": 0.0, "y_m": 1.5},
                "customer_confirmed": True,
            },
        ],
    }


def test_capabilities_report_planar_calibration_without_overclaiming(client):
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["calibration_plane_api_ready"] is True
    assert body["planar_projection_api_ready"] is True
    assert body["preview"]["photo_projection_ready"] is False
    assert body["preview"]["full_camera_calibration_ready"] is False


def test_plane_calibration_endpoint_returns_homography(client):
    response = client.post("/api/v1/calibration/plane", json=_plane_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "calibrated"
    assert body["plane_type"] == "wall"
    assert body["planar_projection_ready"] is True
    assert body["full_camera_calibration_ready"] is False
    assert len(body["homography_m_to_px"]) == 3
    assert len(body["homography_px_to_m"]) == 3


def test_plane_projection_endpoint_maps_metres_to_pixels(client):
    response = client.post(
        "/api/v1/calibration/plane/project",
        json={
            "calibration": _plane_payload(),
            "points_m": [{"x_m": 1.0, "y_m": 0.75}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["calibration"]["status"] == "calibrated"
    assert len(body["projected_points"]) == 1
    assert body["projected_points"][0]["inside_image"] is True
