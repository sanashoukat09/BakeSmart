import base64
import io

import numpy as np
import pytest
from PIL import Image

from training.annotation_workspace import AnnotationWorkspace, LABEL_CLASSES, UNLABELLED_ID


def _workspace(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (8, 6), (200, 190, 180)).save(images / "real-venue-0001.jpg")
    return AnnotationWorkspace(tmp_path)


def _overlay_data_url(size=(8, 6), class_id=0, transparent_pixels=0):
    label = next(item for item in LABEL_CLASSES if item.class_id == class_id)
    rgba = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    rgba[..., :3] = label.rgb
    rgba[..., 3] = 255
    if transparent_pixels:
        rgba.reshape(-1, 4)[:transparent_pixels, 3] = 0
    output = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def test_scene_listing_and_blank_overlay(tmp_path):
    workspace = _workspace(tmp_path)
    scenes = workspace.list_scenes("real_v2")
    assert len(scenes) == 1
    assert scenes[0]["scene_id"] == "real-venue-0001"
    assert scenes[0]["status"] == "not_started"
    overlay = workspace.overlay_png("real_v2", "real-venue-0001")
    with Image.open(io.BytesIO(overlay)) as image:
        pixels = np.asarray(image.convert("RGBA"))
    assert pixels.shape == (6, 8, 4)
    assert np.count_nonzero(pixels[..., 3]) == 0


def test_draft_uses_255_for_unlabelled_pixels(tmp_path):
    workspace = _workspace(tmp_path)
    result = workspace.save_draft(
        "real_v2", "real-venue-0001", _overlay_data_url(transparent_pixels=3), "sana-01"
    )
    assert result["complete"] is False
    assert result["unlabelled_pixels"] == 3
    with Image.open(workspace.mask_path("real_v2", "real-venue-0001")) as mask:
        values = np.asarray(mask.convert("L"))
    assert np.count_nonzero(values == UNLABELLED_ID) == 3
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["status"] == "draft_in_progress"
    assert record["training_status"] == "not_for_training"


def test_completion_requires_every_pixel_and_annotator(tmp_path):
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match="unlabelled"):
        workspace.complete_annotation(
            "real_v2", "real-venue-0001", _overlay_data_url(transparent_pixels=1), "sana-01"
        )
    with pytest.raises(ValueError, match="annotator ID"):
        workspace.complete_annotation(
            "real_v2", "real-venue-0001", _overlay_data_url(), ""
        )


def test_completed_mask_has_only_final_ids_and_pending_review_record(tmp_path):
    workspace = _workspace(tmp_path)
    result = workspace.complete_annotation(
        "real_v2", "real-venue-0001", _overlay_data_url(class_id=3), "sana-01"
    )
    assert result["complete"] is True
    assert result["class_counts"]["window"] == 48
    with Image.open(workspace.mask_path("real_v2", "real-venue-0001")) as mask:
        values = np.unique(np.asarray(mask.convert("L"))).tolist()
    assert values == [3]
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["status"] == "annotation_complete_pending_review"
    assert record["review_status"] == "pending_independent_review"
    assert record["training_status"] == "not_for_training"
    assert record["mask_sha256"]


def test_overlay_must_match_source_dimensions(tmp_path):
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match="exactly match"):
        workspace.decode_overlay(
            "real_v2", "real-venue-0001", _overlay_data_url(size=(4, 4))
        )
