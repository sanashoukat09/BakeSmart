import hashlib
import json

import numpy as np
from PIL import Image

from training.real_venue_model_evaluation import (
    letterbox_image,
    letterbox_mask,
    locked_test_samples,
)
from training.real_venue_segmentation import load_locked_split_manifest


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_letterbox_image_and_mask_share_transform():
    image = Image.new("RGB", (160, 80), (120, 130, 140))
    mask = Image.fromarray(np.ones((80, 160), dtype=np.uint8))
    tensor, transform = letterbox_image(image, canvas_size=64)
    labels = letterbox_mask(mask, transform, scene_id="scene-a")
    assert tensor.shape == (1, 3, 64, 64)
    assert labels.shape == (1, 64, 64)
    assert transform.resized_width == 64
    assert transform.resized_height == 32
    assert int((labels != 255).sum()) == 64 * 32


def test_final_loader_verifies_only_locked_test_rows(tmp_path):
    image = tmp_path / "data" / "test.jpg"
    mask = tmp_path / "data" / "test-mask.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (64, 64), (100, 100, 100)).save(image)
    Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(mask)
    row = {
        "scene_id": "test-a",
        "split": "test",
        "image_path": str(image.relative_to(tmp_path)).replace("\\", "/"),
        "mask_path": str(mask.relative_to(tmp_path)).replace("\\", "/"),
        "image_sha256": _sha(image),
        "mask_sha256": _sha(mask),
        "class_ids_present": [0],
    }
    manifest = {
        "dataset": "real_v2",
        "test_set_locked": True,
        "semantic_class_ids": [0, 1, 2, 3, 4, 5],
        "counts": {"train": 1, "validation": 1, "test": 1},
        "scenes": [
            {**row, "scene_id": "train-a", "split": "train"},
            {**row, "scene_id": "val-a", "split": "validation"},
            row,
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_locked_split_manifest(manifest_path, project_dir=tmp_path)
    samples = locked_test_samples(loaded, project_dir=tmp_path)
    assert [sample.scene_id for sample in samples] == ["test-a"]
