def test_production_asset_summary_is_truthful(client):
    response = client.get("/api/v1/assets/3d/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["manifest_version"] == "production-assets-v1"
    assert body["total_asset_requirements"] == 30
    assert body["mapped_catalog_item_count"] == 30
    assert body["production_ready_count"] == 9
    assert body["target_min_assets"] == 80
    assert body["library_target_met"] is False
    assert body["runtime_external_glb_assembly_ready"] is False
    assert body["pbr_runtime_renderer_ready"] is False


def test_production_asset_catalog_exposes_true_size_and_pbr_rules(client):
    response = client.get("/api/v1/assets/3d/catalog")

    assert response.status_code == 200
    body = response.json()
    assert len(body["assets"]) == 30
    assert len(body["material_profiles"]) == 14
    arch = next(
        item for item in body["assets"]
        if item["catalog_id"] == "backdrop-round-arch"
    )
    assert arch["dimensions"] == {
        "width_m": 2.0,
        "depth_m": 0.55,
        "height_m": 2.2,
    }
    assert arch["max_uniform_scale"] == 1.02
    assert arch["production_status"] == "production_ready"
    assert arch["renderable"] is True


def test_production_asset_validation_reports_missing_planned_glb(client):
    response = client.post(
        "/api/v1/assets/3d/validate",
        json={"asset_id": "prod-backdrop-chiara-panels"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_glb"
    assert body["renderable"] is False


def test_unknown_production_asset_returns_404(client):
    response = client.post(
        "/api/v1/assets/3d/validate",
        json={"asset_id": "prod-not-in-manifest"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_production_asset"
