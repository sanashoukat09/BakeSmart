def test_health_reports_ready_local_model(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "BakeSmart AI",
        "version": "0.6.0",
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


def test_recommendation_returns_three_budget_aware_packages(client, valid_design_request):
    response = client.post("/api/v1/recommendations", json=valid_design_request)

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "stage3-real-catalog-v1"
    assert body["selected_theme_id"] == "floral-romantic"
    assert body["cake"]["source_image_reference"] == "cake-photo-001"
    assert body["cake"]["shape"] == "round"
    assert body["cake"]["tiers"] == 2
    assert set(body["model_signals"]) == {"theme", "cake", "decor", "layout"}
    assert body["costs"]["decoration_cost_pkr"] <= 50_000
    assert body["costs"]["remaining_budget_pkr"] == (
        50_000 - body["costs"]["decoration_cost_pkr"]
    )
    assert body["costs"]["budget_scope"] == "decorations_only"
    assert body["costs"]["pricing_basis"] == (
        "real_catalogue_planning_range_not_vendor_quote"
    )

    roles = {item["role"] for item in body["scene"]["objects"]}
    assert {"cake", "cake_table", "backdrop"} <= roles
    assert body["scene"]["layers"][:2] == [
        "cake_and_baked_items",
        "dessert_table",
    ]
    assert "backdrop" in body["scene"]["layers"]
    assert body["preview"] == {
        "interactive_3d_ready": True,
        "viewer_3d_url": f"/viewer/{body['design_id']}",
        "viewer_label": "Open Basic 3D Layout Preview",
        "scene_glb_url": f"/api/v1/designs/{body['design_id']}/scene.glb",
        "ar_supported": None,
        "ar_url": None,
        "fallback_label": None,
    }
    assert body["scene"]["asset_status"] == "generated_procedural_glb"
    assert body["scene"]["concept_not_to_scale"] is False
    assert any("real catalogue price ranges" in warning for warning in body["warnings"])
    assert body["venue_assessment"]["placement_status"] == "clearance_verified"
    assert body["venue_assessment"]["evidence_confidence"] == "medium"
    assert body["venue_assessment"]["available_front_clearance_m"] == 1.575
    assert body["venue_assessment"]["obstacle_map_confirmed"] is True
    assert [item["package_id"] for item in body["packages"]] == [
        "essential",
        "balanced",
        "statement",
    ]
    assert body["recommended_package_id"] == "balanced"
    assert sum(item["recommended"] for item in body["packages"]) == 1
    assert len({len(item["decorations"]) for item in body["packages"]}) >= 2
    assert all(
        item["decoration_cost_pkr"] <= item["budget_pkr"]
        for item in body["packages"]
    )


def test_recommendation_id_is_deterministic(client, valid_design_request):
    first = client.post("/api/v1/recommendations", json=valid_design_request)
    second = client.post("/api/v1/recommendations", json=valid_design_request)

    assert first.status_code == second.status_code == 200
    assert first.json()["design_id"] == second.json()["design_id"]


def test_viewer_and_glb_urls_are_real_local_resources(client, valid_design_request):
    recommendation = client.post(
        "/api/v1/recommendations", json=valid_design_request
    ).json()

    viewer = client.get(recommendation["preview"]["viewer_3d_url"])
    glb = client.get(recommendation["preview"]["scene_glb_url"])
    viewer_script = client.get("/static/viewer.js")

    assert viewer.status_code == 200
    assert viewer.headers["content-type"].startswith("text/html")
    assert "default-src 'self'" in viewer.headers["content-security-policy"]
    assert b'id="scene-canvas"' in viewer.content
    assert b"https://" not in viewer.content
    assert b'/static/viewer.js?v=20260825-1' in viewer.content
    assert glb.status_code == 200
    assert glb.headers["content-type"] == "model/gltf-binary"
    assert glb.headers["cache-control"] == "private, no-cache"
    assert glb.content[:4] == b"glTF"
    assert viewer_script.status_code == 200
    assert b"pointermove" in viewer_script.content
    assert b"wheel" in viewer_script.content
    assert b"distanceBetweenPointers" in viewer_script.content
    assert viewer_script.content.count(b"precision mediump float;") == 2


def test_unknown_viewer_scene_returns_not_found(client):
    viewer = client.get("/viewer/design-00000000000000000000")
    glb = client.get("/api/v1/designs/design-00000000000000000000/scene.glb")
    invalid = client.get("/viewer/not-a-design")
    preview = client.get(
        "/api/v1/designs/design-00000000000000000000/previews/unknown.png"
    )

    assert viewer.status_code == 404
    assert glb.status_code == 404
    assert invalid.status_code == 404
    assert preview.status_code == 404
