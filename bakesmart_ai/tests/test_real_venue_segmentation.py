import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch")

from training.real_venue_segmentation import (
    BakeSmartVenueUNet,
    SegmentationConfusion,
    letterbox_pair,
    load_locked_split_manifest,
    samples_for_split,
)


def _manifest(tmp_path: Path) -> Path:
    payload = {
        "dataset": "real_v2",
        "test_set_locked": True,
        "semantic_class_ids": [0, 1, 2, 3, 4, 5],
        "counts": {"train": 1, "validation": 1, "test": 1},
        "scenes": [
            {"scene_id": "train-1", "split": "train"},
            {"scene_id": "val-1", "split": "validation"},
            {"scene_id": "test-1", "split": "test"},
        ],
    }
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_model_outputs_six_classes_at_input_resolution():
    model = BakeSmartVenueUNet(base_channels=8)
    x = torch.randn(1, 3, 64, 64)
    with torch.no_grad():
        logits = model(x)
    assert logits.shape == (1, 6, 64, 64)


def test_letterbox_uses_unlabelled_padding_and_nearest_mask_resize():
    image = Image.new("RGB", (80, 40), (20, 30, 40))
    mask_array = np.zeros((40, 80), dtype=np.uint8)
    mask_array[:, 40:] = 1
    mask = Image.fromarray(mask_array)
    resized_image, resized_mask = letterbox_pair(image, mask, 64)
    assert resized_image.size == (64, 64)
    labels = np.asarray(resized_mask)
    assert set(np.unique(labels)).issubset({0, 1, 255})
    assert np.all(labels[:16] == 255)
    assert np.all(labels[48:] == 255)


def test_locked_manifest_is_required(tmp_path):
    path = _manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["test_set_locked"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="test_set_locked"):
        load_locked_split_manifest(path, project_dir=tmp_path)


def test_step4_refuses_to_load_test_samples(tmp_path):
    path = _manifest(tmp_path)
    manifest = load_locked_split_manifest(path, project_dir=tmp_path)
    with pytest.raises(ValueError, match="reserved for final evaluation"):
        samples_for_split(manifest, "test", project_dir=tmp_path, verify_hashes=False)


def test_perfect_predictions_have_perfect_metrics():
    truth = torch.tensor([[[0, 1, 2], [3, 4, 5]]], dtype=torch.int64)
    prediction = truth.clone()
    confusion = SegmentationConfusion()
    confusion.update(truth, prediction)
    metrics = confusion.metrics()
    assert metrics["pixel_accuracy"] == 1.0
    assert metrics["mean_iou"] == 1.0
    for name in ("wall", "floor", "door", "window", "furniture", "outlet"):
        assert metrics["per_class"][name]["iou"] == 1.0
