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


def test_unknown_theme_uses_model_guided_catalog_fallback(client, valid_design_request):
    request = deepcopy(valid_design_request)
    request["event"]["theme_id"] = "not-in-catalog"

    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["selected_theme_id"] != "not-in-catalog"
    assert any("model-guided fallback" in warning for warning in body["warnings"])
