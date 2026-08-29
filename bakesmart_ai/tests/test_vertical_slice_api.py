def test_vertical_slice_summary_endpoint_is_review_only(client):
    response = client.get("/api/v1/assets/3d/vertical-slice")
    assert response.status_code == 200
    body = response.json()
    assert body["slice_version"] == "professional-vertical-slice-v1"
    assert body["geometry_review_assets_present"] is True
    assert body["customer_runtime_ready"] is False
    assert len(body["celebrations"]) == 3


def test_vertical_slice_compose_endpoint_preserves_true_scale(client):
    response = client.post(
        "/api/v1/assets/3d/vertical-slice/compose",
        json={
            "celebration": "wedding",
            "usable_focal_width_m": 5.0,
            "target_visual_width_m": 4.2,
            "include_lighting": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["true_size_only"] is True
    assert body["review_only"] is True
    assert all(item["uniform_scale"] == 1.0 for item in body["placements"])


def test_review_glb_endpoint_serves_generated_prototype(client):
    response = client.get(
        "/api/v1/assets/3d/review/prod-backdrop-chiara-panels.glb"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("model/gltf-binary")
    assert response.headers["x-bakesmart-review-only"] == "true"
    assert response.content[:4] == b"glTF"
