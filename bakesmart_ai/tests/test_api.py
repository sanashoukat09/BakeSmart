def test_health_reports_ready_local_model(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "BakeSmart AI",
        "version": "0.2.0",
        "model_status": "ready",
    }


def test_capabilities_use_metres_and_pkr(client):
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["canonical_units"] == "metres"
    assert body["currency"] == "PKR"
    assert body["model_ready"] is True
    assert "room" in body["area_types"]
    assert "kids_birthday" in body["event_types"]


def test_valid_design_request_is_normalized(client, valid_design_request):
    response = client.post("/api/v1/designs/validate", json=valid_design_request)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["normalized_request"]["event"]["theme_id"] == "floral-romantic"
    assert body["normalized_request"]["minimum_clearance_m"] == 0.9
    assert len(body["warnings"]) == 1


def test_recommendation_returns_one_budget_aware_scene(client, valid_design_request):
    response = client.post("/api/v1/recommendations", json=valid_design_request)

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "bootstrap-v1"
    assert body["selected_theme_id"] == "floral-romantic"
    assert body["cake"]["source_image_reference"] == "cake-photo-001"
    assert set(body["model_signals"]) == {"theme", "cake", "decor", "layout"}
    assert body["costs"]["decoration_cost_pkr"] <= 50_000
    assert body["costs"]["remaining_budget_pkr"] == (
        50_000 - body["costs"]["decoration_cost_pkr"]
    )
    assert body["costs"]["budget_scope"] == "decorations_only"
    assert body["costs"]["pricing_basis"] == (
        "synthetic_planning_estimate_not_vendor_quote"
    )

    roles = {item["role"] for item in body["scene"]["objects"]}
    assert {"cake", "cake_table", "backdrop", "decoration", "lighting"} <= roles
    assert body["scene"]["layers"] == [
        "cake_and_baked_items",
        "dessert_table",
        "decorations",
        "backdrop",
        "lighting",
    ]
    assert body["preview"] == {
        "interactive_3d_ready": False,
        "viewer_3d_url": None,
        "ar_supported": None,
        "ar_url": None,
        "fallback_label": "Concept preview—not to scale",
    }
    assert body["scene"]["concept_not_to_scale"] is True
    assert any("synthetic labels" in warning for warning in body["warnings"])
    assert any("No obstacle map" in warning for warning in body["warnings"])


def test_recommendation_id_is_deterministic(client, valid_design_request):
    first = client.post("/api/v1/recommendations", json=valid_design_request)
    second = client.post("/api/v1/recommendations", json=valid_design_request)

    assert first.status_code == second.status_code == 200
    assert first.json()["design_id"] == second.json()["design_id"]
