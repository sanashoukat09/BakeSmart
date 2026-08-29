def test_capabilities_report_metric_room_constraint_engine(client):
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["metric_room_constraints_ready"] is True
    assert body["scale_aware_scene_fitting_ready"] is True
    assert body["preview"]["full_camera_calibration_ready"] is False


def test_room_constraint_endpoint_returns_verified_scale_targets(
    client,
    valid_design_request,
):
    response = client.post(
        "/api/v1/constraints/room",
        json={
            "space": valid_design_request["space"],
            "minimum_clearance_m": 0.9,
            "objects": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["hard_constraints_ready"] is True
    assert body["largest_focal_zone"]["width_m"] > 2.0
    assert body["scale_targets"]["recommended_backdrop_width_m"] > 1.5
    assert body["available_front_clearance_m"] == 2.4
