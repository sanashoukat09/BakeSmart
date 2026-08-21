import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from training.annotation_workspace import AnnotationWorkspace
from training.smart_annotation import SmartAnnotationService, SmartObjectResult
from training.venue_labeler import create_app


def _workspace(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (40, 30), (190, 180, 170)).save(images / "real-venue-0001.jpg")
    return AnnotationWorkspace(tmp_path)


def test_smart_rectangle_is_clipped_to_image_bounds():
    rectangle = SmartAnnotationService._normalize_rectangle(
        x=-4,
        y=3,
        width=20,
        height=15,
        image_width=40,
        image_height=30,
    )
    assert rectangle == (0, 3, 16, 15)


def test_smart_rectangle_rejects_tiny_boxes():
    with pytest.raises(ValueError, match="at least 5×5"):
        SmartAnnotationService._normalize_rectangle(
            x=3,
            y=3,
            width=2,
            height=3,
            image_width=40,
            image_height=30,
        )


def test_component_filter_keeps_only_seed_connected_region():
    import numpy as np

    selected = np.zeros((8, 10), dtype=np.uint8)
    selected[1:4, 1:4] = 1
    selected[5:7, 7:9] = 1
    seed = np.zeros_like(selected)
    seed[2, 2] = 1
    kept = SmartAnnotationService._keep_components_touching_seed(selected, seed)
    assert int(kept.sum()) == 9
    assert kept[2, 2] == 1
    assert kept[5, 7] == 0


class _FakeSmartService:
    def smart_object(self, **kwargs):
        mask = Image.new("L", (40, 30), 0)
        for x in range(10, 20):
            for y in range(8, 18):
                mask.putpixel((x, y), 255)
        buffer = io.BytesIO()
        mask.save(buffer, format="PNG")
        return SmartObjectResult(
            png_bytes=buffer.getvalue(),
            selected_pixels=100,
            rectangle=(10, 8, 10, 10),
        )


def test_smart_object_endpoint_returns_binary_png(tmp_path):
    workspace = _workspace(tmp_path)
    app = create_app(
        workspace=workspace,
        smart_annotation_service=_FakeSmartService(),
        static_dir=None,
    )
    client = TestClient(app)
    response = client.post(
        "/api/scenes/real_v2/real-venue-0001/smart-object",
        json={"x": 10, "y": 8, "width": 10, "height": 10},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-selected-pixels"] == "100"
    with Image.open(io.BytesIO(response.content)) as mask:
        assert mask.size == (40, 30)
        assert mask.convert("L").getpixel((12, 12)) == 255
