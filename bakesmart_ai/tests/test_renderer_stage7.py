def test_stage7_renderer_capabilities_are_truthful(client):
    response = client.get("/api/v1/assets/3d/renderer/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["renderer_version"] == "professional-webgl-v1"
    assert body["local_only"] is True
    assert body["external_runtime_dependencies"] is False
    assert body["multi_glb_modules"] is True
    assert body["multi_node_mesh"] is True
    assert body["pbr_metallic_roughness_factors"] is True
    assert body["base_color_texture"] is True
    assert body["metallic_roughness_texture"] is True
    assert body["emissive_texture"] is True
    assert body["normal_map_texture"] is False
    assert body["object_selection"] is True
    assert body["metric_module_transforms"] is True
    assert body["runtime_lod_switching"] is False
    assert body["customer_production_modular_scene_ready"] is False


def test_birthday_modular_scene_manifest_keeps_true_scale(client):
    response = client.get(
        "/api/v1/assets/3d/vertical-slice/scene",
        params={
            "celebration": "birthday",
            "usable_focal_width_m": 5.5,
            "target_visual_width_m": 4.5,
            "include_lighting": "true",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scene_version"] == "professional-modular-review-v1"
    assert body["review_only"] is True
    assert body["true_size_only"] is True
    assert body["customer_runtime_ready"] is False
    assert body["modules"]
    assert all(module["uniform_scale"] == 1.0 for module in body["modules"])
    assert all(
        module["glb_url"].startswith("/api/v1/assets/3d/review/prod-")
        for module in body["modules"]
    )
    assert all(len(module["translation_m"]) == 3 for module in body["modules"])
    assert body["viewer_url"].startswith("/viewer/vertical-slice/birthday?")


def test_mehndi_scene_refuses_to_shrink_true_size_stage(client):
    response = client.get(
        "/api/v1/assets/3d/vertical-slice/scene",
        params={
            "celebration": "south_asian_mehndi",
            "usable_focal_width_m": 4.4,
            "target_visual_width_m": 4.0,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "does_not_fit"
    assert body["modules"] == []
    assert body["true_size_only"] is True


def test_vertical_slice_review_viewer_is_served(client):
    response = client.get("/viewer/vertical-slice/wedding")

    assert response.status_code == 200
    assert response.headers["x-bakesmart-review-only"] == "true"
    assert "Professional Modular 3D Review" in response.text
    assert "/static/renderer_core.js" in response.text


def test_unknown_vertical_slice_review_viewer_returns_404(client):
    response = client.get("/viewer/vertical-slice/not-a-slice")

    assert response.status_code == 404


def test_renderer_core_is_local_and_exposes_multi_module_class(client):
    response = client.get("/static/renderer_core.js")

    assert response.status_code == 200
    assert "BakeSmartProfessionalRenderer" in response.text
    assert "pbrMetallicRoughness" in response.text
    assert "https://" not in response.text
    assert "http://" not in response.text
