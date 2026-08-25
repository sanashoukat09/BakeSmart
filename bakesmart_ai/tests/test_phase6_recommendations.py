from copy import deepcopy


def test_low_budget_never_overspends(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["decoration_budget_pkr"] = 3_000

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["costs"]["decoration_cost_pkr"] <= 3_000
    assert body["costs"]["remaining_budget_pkr"] >= 0
    assert any("did not fit" in warning for warning in body["warnings"])


def test_excluded_decor_categories_are_not_returned(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["event"]["required_decor_categories"] = []
    request["event"]["excluded_decor_categories"] = [
        "backdrop",
        "floor-arrangement",
        "lighting",
        "table-setting",
        "signage",
    ]

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["decorations"] == []
    assert body["costs"]["decoration_cost_pkr"] == 0
    assert {item["role"] for item in body["scene"]["objects"]} == {
        "cake",
        "cake_table",
    }


def test_blocking_obstacle_requires_manual_review(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["space"]["obstacles"] = [
        {
            "obstacle_type": "door",
            "label": "main door",
            "position": {"x_m": 0, "y_m": 0, "z_m": 0},
            "dimensions": {"width_m": 3, "depth_m": 0.2, "height_m": 2.1},
        }
    ]

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["scene"]["concept_not_to_scale"] is True
    assert body["venue_assessment"]["placement_status"] == "manual_review_required"
    assert "main door" in body["venue_assessment"]["blocking_obstacles"]
    assert any("No obstacle-free focal position" in item for item in body["warnings"])


def test_measured_clear_scene_can_be_scale_planned(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["space"]["obstacles"] = [
        {
            "obstacle_type": "furniture",
            "label": "rear sofa",
            "position": {"x_m": 0, "y_m": 2.0, "z_m": 0},
            "dimensions": {"width_m": 0.3, "depth_m": 0.1, "height_m": 0.8},
        }
    ]

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    assert response.json()["scene"]["concept_not_to_scale"] is False


def test_two_good_photo_angles_raise_evidence_confidence(
    client,
    valid_design_request,
):
    request = deepcopy(valid_design_request)
    second = deepcopy(request["space"]["photo_evidence"][0])
    second["photo_id"] = "venue-photo-fedcba9876543210fedc"
    second["angle"] = "second_angle"
    request["space"]["photo_evidence"].append(second)
    request["space"]["photo_references"].append(second["photo_id"])

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    assessment = response.json()["venue_assessment"]
    assert assessment["photo_count"] == 2
    assert assessment["evidence_confidence"] == "high"
    assert assessment["assumptions"] == [
        "Photo analysis does not automatically identify safety-critical objects."
    ]


def test_vision_candidate_is_reported_but_not_used_as_obstacle(
    client,
    valid_design_request,
):
    request = deepcopy(valid_design_request)
    evidence = request["space"]["photo_evidence"][0]
    evidence["vision_model_version"] = "venue-vision-bootstrap-v1"
    evidence["unconfirmed_candidates"] = [
        {
            "label": "door",
            "confidence": 0.49,
            "bounding_box": [0.1, 0.2, 0.2, 0.6],
            "area_fraction": 0.12,
            "confirmed": False,
            "source": "synthetic_bootstrap_model",
        }
    ]

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    assessment = response.json()["venue_assessment"]
    assert assessment["obstacle_count"] == 0
    assert assessment["placement_status"] == "clearance_verified"
    assert any(
        "possible door" in assumption and "none were used" in assumption
        for assumption in assessment["assumptions"]
    )


def test_manual_outlet_marks_are_preserved_without_false_scale_claim(
    client,
    valid_design_request,
):
    request = deepcopy(valid_design_request)
    request["space"]["photo_evidence"][0]["manual_outlets"] = [
        {
            "x_fraction": 0.72,
            "y_fraction": 0.61,
            "source": "customer_manual",
        }
    ]

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    body = response.json()
    assert any(
        "manually marked 1 visible Outlet" in fact
        for fact in body["venue_assessment"]["observed_facts"]
    )
    assert any(
        "not measured 3D obstacles" in assumption
        for assumption in body["venue_assessment"]["assumptions"]
    )
    assert any(
        "Add each relevant Outlet as a measured obstacle" in warning
        for warning in body["warnings"]
    )


def test_unknown_theme_uses_model_guided_catalog_fallback(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["event"]["theme_id"] = "not-in-catalog"

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["selected_theme_id"] != "not-in-catalog"
    assert any("model-guided fallback" in warning for warning in body["warnings"])
