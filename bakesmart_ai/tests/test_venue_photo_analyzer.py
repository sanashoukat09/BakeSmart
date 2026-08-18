import base64
from io import BytesIO

import numpy as np
from PIL import Image


def _venue_photo_base64(width: int = 1280, height: int = 720) -> str:
    rows = np.arange(height, dtype=np.uint16)[:, None]
    columns = np.arange(width, dtype=np.uint16)[None, :]
    checker = ((rows // 24 + columns // 24) % 2) * 45
    pixels = np.clip(85 + checker + (rows > height * 0.62) * 55, 0, 255)
    rgb = np.repeat(pixels[:, :, None], 3, axis=2).astype(np.uint8)
    output = BytesIO()
    Image.fromarray(rgb).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_venue_photo_is_analysed_locally_without_scale_claim(client):
    response = client.post(
        "/api/v1/venue-photos/analyze",
        json={
            "file_name": "living-room.png",
            "media_type": "image/png",
            "image_base64": _venue_photo_base64(),
            "angle": "wide",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["photo_id"].startswith("venue-photo-")
    assert body["angle"] == "wide"
    assert body["pixel_width"] == 1280
    assert body["pixel_height"] == 720
    assert body["orientation"] == "landscape"
    assert body["quality"] in {"high", "medium"}
    assert body["horizontal_structure_score"] > 0
    assert body["exact_scale_available"] is False
    assert body["persisted"] is False
    assert "image_base64" not in body
    assert any("not persisted" in item for item in body["limitations"])
    assert any("automatically confirmed" in item for item in body["limitations"])


def test_invalid_photo_payload_is_rejected_with_clear_error(client):
    response = client.post(
        "/api/v1/venue-photos/analyze",
        json={
            "file_name": "not-a-photo.png",
            "media_type": "image/png",
            "image_base64": base64.b64encode(b"not an image").decode("ascii"),
            "angle": "wide",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_venue_photo"


def test_declared_media_type_must_match_photo_content(client):
    response = client.post(
        "/api/v1/venue-photos/analyze",
        json={
            "file_name": "living-room.jpg",
            "media_type": "image/jpeg",
            "image_base64": _venue_photo_base64(),
            "angle": "second_angle",
        },
    )

    assert response.status_code == 422
    assert "media type" in response.json()["detail"]["message"]
