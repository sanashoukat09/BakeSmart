def test_health_reports_untrained_model(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "BakeSmart AI",
        "version": "0.1.0",
        "model_status": "not_trained",
    }


def test_capabilities_use_metres_and_pkr(client):
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["canonical_units"] == "metres"
    assert body["currency"] == "PKR"
    assert body["model_ready"] is False
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


def test_recommendation_is_disabled_until_training(client, valid_design_request):
    response = client.post("/api/v1/recommendations", json=valid_design_request)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_not_trained"
