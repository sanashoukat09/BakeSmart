from copy import deepcopy


def test_room_requires_depth(client, valid_design_request):
    request = deepcopy(valid_design_request)
    del request["space"]["dimensions"]["depth_m"]

    response = client.post("/api/v1/designs/validate", json=request)

    assert response.status_code == 422
    assert "depth_m is required" in response.text


def test_round_cake_requires_diameter(client, valid_design_request):
    request = deepcopy(valid_design_request)
    del request["cake"]["diameter_m"]

    response = client.post("/api/v1/designs/validate", json=request)

    assert response.status_code == 422
    assert "diameter_m is required" in response.text


def test_clearance_cannot_be_less_than_ninety_centimetres(
    client,
    valid_design_request,
):
    request = deepcopy(valid_design_request)
    request["minimum_clearance_m"] = 0.5

    response = client.post("/api/v1/designs/validate", json=request)

    assert response.status_code == 422


def test_obstacle_must_fit_inside_confirmed_space(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["space"]["obstacles"] = [
        {
            "obstacle_type": "door",
            "label": "outside door",
            "position": {"x_m": 2.8, "y_m": 0, "z_m": 0},
            "dimensions": {"width_m": 0.9, "depth_m": 0.2, "height_m": 2.1},
        }
    ]

    response = client.post("/api/v1/designs/validate", json=request)

    assert response.status_code == 422
    assert "exceeds the measured width" in response.text


def test_duplicate_photo_angles_are_rejected(client, valid_design_request):
    request = deepcopy(valid_design_request)
    duplicate = deepcopy(request["space"]["photo_evidence"][0])
    duplicate["photo_id"] = "venue-photo-fedcba9876543210fedc"
    request["space"]["photo_evidence"].append(duplicate)

    response = client.post("/api/v1/designs/validate", json=request)

    assert response.status_code == 422
    assert "only one photo per angle" in response.text


def test_vision_candidate_cannot_be_marked_confirmed(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["space"]["photo_evidence"][0]["unconfirmed_candidates"] = [
        {
            "label": "door",
            "confidence": 0.49,
            "bounding_box": [0.1, 0.2, 0.2, 0.6],
            "area_fraction": 0.12,
            "confirmed": True,
            "source": "synthetic_bootstrap_model",
        }
    ]

    response = client.post("/api/v1/designs/validate", json=request)

    assert response.status_code == 422
    assert "Input should be False" in response.text
