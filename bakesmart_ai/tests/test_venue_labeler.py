import base64
import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from training.annotation_workspace import AnnotationWorkspace, LABEL_CLASSES
from training.venue_labeler import create_app


def _client(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (6, 4), (180, 170, 160)).save(images / "real-venue-0001.jpg")
    app = create_app(workspace=AnnotationWorkspace(tmp_path), static_dir=None)
    return TestClient(app)


def _complete_overlay():
    label = LABEL_CLASSES[1]
    rgba = np.zeros((4, 6, 4), dtype=np.uint8)
    rgba[..., :3] = label.rgb
    rgba[..., 3] = 255
    output = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def test_api_lists_classes_datasets_and_scenes(tmp_path):
    client = _client(tmp_path)
    classes = client.get("/api/label-classes")
    assert classes.status_code == 200
    assert [item["id"] for item in classes.json()["classes"]] == list(range(7))
    scenes = client.get("/api/scenes?dataset=real_v2")
    assert scenes.status_code == 200
    assert scenes.json()["scenes"][0]["scene_id"] == "real-venue-0001"


def test_api_validates_and_completes_mask(tmp_path):
    client = _client(tmp_path)
    payload = {"mask_png_base64": _complete_overlay(), "annotator_id": "sana-01"}
    validation = client.post(
        "/api/scenes/real_v2/real-venue-0001/validate", json=payload
    )
    assert validation.status_code == 200
    assert validation.json()["complete"] is True
    completed = client.post(
        "/api/scenes/real_v2/real-venue-0001/complete", json=payload
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "annotation_complete_pending_review"


def test_api_rejects_unknown_dataset(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/scenes?dataset=unknown")
    assert response.status_code == 404
