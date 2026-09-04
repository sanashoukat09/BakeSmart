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
    assert body["ai_runtime"] == "local_only"
    assert body["core_training_policy"] == "from_scratch_random_initialization"
    assert body["external_ai_provider"] == "none"
    assert body["scale_source"] == (
        "customer_confirmed_measurements_and_reference_points"
    )
    assert body["calibration_reference_api_ready"] is True
    assert body["preview"] == {
        "geometry_mode": "procedural_planning_geometry",
        "asset_mode": "generated_procedural_glb",
        "renderer_mode": "local_webgl",
        "material_mode": "vertex_color_lit",
        "metric_scene_coordinates": True,
        "camera_navigation_ready": True,
        "photo_projection_ready": False,
        "full_camera_calibration_ready": False,
        "object_editing_ready": False,
    }
    assert "room" in body["area_types"]
    assert "kids_birthday" in body["event_types"]


def test_calibration_reference_uses_only_customer_confirmed_measurement(client):
    response = client.post(
        "/api/v1/calibration/reference",
        json={
            "image_width_px": 1000,
            "image_height_px": 500,
            "reference": {
                "photo_id": "venue-photo-0123456789abcdef0123",
                "label": "Measured table edge",
                "start": {"x_fraction": 0.1, "y_fraction": 0.5},
                "end": {"x_fraction": 0.5, "y_fraction": 0.5},
                "known_length_m": 2.0,
                "plane": "table",
                "customer_confirmed": True,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reference_recorded"
    assert body["segment_length_px"] == 400.0
    assert body["pixels_per_m_along_reference"] == 200.0
    assert body["metric_reference_ready"] is True
    assert body["global_projection_ready"] is False
    assert body["scale_source"] == "customer_confirmed_reference"


def test_valid_design_request_is_normalized(client, valid_design_request):
    response = client.post("/api/v1/designs/validate", json=valid_design_request)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["normalized_request"]["event"]["theme_id"] == "floral-romantic"
    assert body["normalized_request"]["minimum_clearance_m"] == 0.9
    assert len(body["warnings"]) == 2
    assert any("does not camera-calibrate" in warning for warning in body["warnings"])


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
        "viewer_3d_url": f"/viewer/{body['design_id']}?package=balanced",
        "viewer_label": "Open Detailed 3D View",
        "scene_glb_url": f"/api/v1/designs/{body['design_id']}/scene.glb",
        "ar_supported": None,
        "ar_url": None,
        "fallback_label": None,
    }
    assert body["scene"]["asset_status"] == (
        "production_modular_glbs_with_procedural_fallback"
    )
    assert body["scene"]["concept_not_to_scale"] is False
    assert any("real catalogue price ranges" in warning for warning in body["warnings"])
    assert any("not a camera-calibrated" in warning for warning in body["warnings"])
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
    renderer_core = client.get("/static/renderer_core.js")
    modules = client.get(f"/api/v1/designs/{recommendation['design_id']}/modules.json")

    assert viewer.status_code == 200
    assert viewer.headers["content-type"].startswith("text/html")
    assert "default-src 'self'" in viewer.headers["content-security-policy"]
    assert b'id="scene-canvas"' in viewer.content
    assert b"https://" not in viewer.content
    assert b'/static/viewer.js?v=20260829-7' in viewer.content
    assert b"3D Planning Preview" in viewer.content
    assert b"PBR materials" not in viewer.content
    assert b"camera-calibrated" in viewer.content
    assert glb.status_code == 200
    assert glb.headers["content-type"] == "model/gltf-binary"
    assert glb.headers["cache-control"] == "private, no-cache"
    assert glb.content[:4] == b"glTF"
    assert viewer_script.status_code == 200
    assert renderer_core.status_code == 200
    assert modules.status_code == 200
    assert modules.json()["scene_version"] == "customer-production-modular-v1"
    assert modules.json()["production_module_count"] == 1
    assert modules.json()["modules"][0]["asset_id"] == "prod-table-low-floral"
    assert modules.json()["modules"][0]["uniform_scale"] == 1.0
    assert b"pointermove" in renderer_core.content
    assert b"wheel" in renderer_core.content
    assert b"pbrMetallicRoughness" in renderer_core.content
    assert b"uShadowPass" in renderer_core.content
    assert b"photo-fallback" in viewer.content
    assert renderer_core.content.count(b"precision highp float;") == 2


def test_unapproved_production_glb_is_never_customer_served(client):
    response = client.get(
        "/api/v1/assets/3d/production/prod-sign-mirror-welcome.glb"
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "production_asset_not_customer_ready"
    )


def test_unknown_viewer_scene_returns_not_found(client):
    viewer = client.get("/viewer/design-00000000000000000000")
    glb = client.get("/api/v1/designs/design-00000000000000000000/scene.glb")
    invalid = client.get("/viewer/not-a-design")
    preview = client.get(
        "/api/v1/designs/design-00000000000000000000/previews/unknown.png"
    )
    preview_page = client.get(
        "/preview/design-00000000000000000000/unknown"
    )

    assert viewer.status_code == 404
    assert glb.status_code == 404
    assert invalid.status_code == 404
    assert preview.status_code == 404
    assert preview_page.status_code == 404


def test_cake_reference_review_resources_are_fixed_and_review_only(client):
    catalog = client.get("/api/v1/assets/3d/cake-references")
    viewer = client.get("/viewer/cake-references/review")

    assert catalog.status_code == 200
    body = catalog.json()
    assert body["reference_only"] is True
    assert body["production_ready"] is False
    assert len(body["assets"]) == 2
    assert all(asset["configurable"] is False for asset in body["assets"])
    for asset in body["assets"]:
        glb = client.get(asset["glb_url"])
        assert glb.status_code == 200
        assert glb.content[:4] == b"glTF"
        assert glb.headers["x-bakesmart-reference-only"] == "true"
        assert glb.headers["x-bakesmart-production-ready"] == "false"
    assert viewer.status_code == 200
    assert b"Realistic Cake Reference Review" in viewer.content
    assert b"not customer-configurable assets" in viewer.content
    assert client.get("/api/v1/assets/3d/cake-references/not-real.glb").status_code == 404
