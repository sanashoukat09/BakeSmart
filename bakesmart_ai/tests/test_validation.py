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
