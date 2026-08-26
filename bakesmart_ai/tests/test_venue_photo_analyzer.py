import base64
from copy import deepcopy
from io import BytesIO

import numpy as np
from PIL import Image

from app.schemas.design import VenuePhotoAnalysisRequest
from app.services.venue_photo_analyzer import VenuePhotoAnalyzer
from training.venue_vision_runtime import VenueVisionCandidate as RuntimeCandidate


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
    assert body["vision_model_version"] == "venue-vision-bootstrap-v1"
    assert body["unconfirmed_candidates"]
    assert all(
        candidate["confirmed"] is False
        and candidate["confidence"] < 0.5
        and candidate["source"] == "synthetic_bootstrap_model"
        for candidate in body["unconfirmed_candidates"]
    )
    assert body["exact_scale_available"] is False
    assert body["persisted"] is False
    assert body["temporarily_stored"] is True
    assert body["temporary_storage_expires_at"]
    assert body["manual_outlets"] == []
    assert "image_base64" not in body
    assert any("up to 24 hours" in item for item in body["limitations"])
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


def test_stage1_uses_temporary_photos_for_three_concept_previews(
    client,
    valid_design_request,
):
    encoded = _venue_photo_base64()
    venue = client.post(
        "/api/v1/venue-photos/analyze",
        json={
            "file_name": "venue.png",
            "media_type": "image/png",
            "image_base64": encoded,
            "angle": "wide",
        },
    )
    cake = client.post(
        "/api/v1/design-assets/cake",
        json={
            "file_name": "cake.png",
            "media_type": "image/png",
            "image_base64": encoded,
        },
    )
    assert venue.status_code == cake.status_code == 200
    assert cake.json()["asset_id"].startswith("cake-photo-")
    assert cake.json()["persisted_permanently"] is False

    request = deepcopy(valid_design_request)
    request["space"]["photo_references"] = [venue.json()["photo_id"]]
    request["space"]["photo_evidence"][0]["photo_id"] = venue.json()["photo_id"]
    request["cake"]["cake_image_reference"] = cake.json()["asset_id"]
    response = client.post("/api/v1/recommendations", json=request)

    assert response.status_code == 200
    packages = response.json()["packages"]
    assert len(packages) == 3
    assert all(package["photo_preview_url"] for package in packages)
    for package in packages:
        preview = client.get(package["photo_preview_url"])
        assert preview.status_code == 200
        assert preview.headers["content-type"].startswith("text/html")
        assert "default-src 'self'" in preview.headers["content-security-policy"]
        assert b'id="preview-image"' in preview.content
        package_id = package["package_id"]
        image = client.get(
            f"/api/v1/designs/{response.json()['design_id']}/previews/"
            f"{package_id}.png"
        )
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.content.startswith(b"\x89PNG")


def test_reviewed_real_runtime_is_preferred_and_reported_honestly():
    class FakeRealRuntime:
        model_version = "venue-vision-real-six-class-test"

        @staticmethod
        def candidates(_image):
            return [
                RuntimeCandidate(
                    label="door",
                    confidence=0.49,
                    bounding_box=(0.1, 0.1, 0.2, 0.6),
                    area_fraction=0.12,
                )
            ]

    analyzer = VenuePhotoAnalyzer()
    analyzer.final_vision_runtime = None
    analyzer.real_vision_runtime = FakeRealRuntime()
    result = analyzer.analyze(
        VenuePhotoAnalysisRequest(
            file_name="room.png",
            media_type="image/png",
            image_base64=_venue_photo_base64(),
            angle="wide",
        )
    )
    assert result.vision_model_version == "venue-vision-real-six-class-test"
    assert result.unconfirmed_candidates[0].source == "reviewed_real_six_class_model"
    assert result.unconfirmed_candidates[0].confirmed is False
    assert result.exact_scale_available is False
    assert any("Walkway is derived" in line for line in result.limitations)


def test_validation_only_v6_bundle_is_preferred_and_keeps_outlets_manual():
    class FakeFinalRuntime:
        model_version = "venue-vision-v6-validation-bundle"

        @staticmethod
        def candidates(_image):
            return [
                RuntimeCandidate(
                    label="door",
                    confidence=0.49,
                    bounding_box=(0.1, 0.1, 0.2, 0.6),
                    area_fraction=0.12,
                )
            ]

    analyzer = VenuePhotoAnalyzer()
    analyzer.final_vision_runtime = FakeFinalRuntime()
    analyzer.real_vision_runtime = None
    result = analyzer.analyze(
        VenuePhotoAnalysisRequest(
            file_name="room.png",
            media_type="image/png",
            image_base64=_venue_photo_base64(),
            angle="wide",
        )
    )
    assert result.vision_model_version == "venue-vision-v6-validation-bundle"
    assert result.unconfirmed_candidates[0].source == "validation_only_v6_bundle"
    assert result.unconfirmed_candidates[0].confirmed is False
    assert result.manual_outlets == []
    assert any("Outlet marking remains manual" in line for line in result.limitations)
