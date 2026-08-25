from pathlib import Path

import numpy as np
from PIL import Image
import torch

from training.real_venue_segmentation import SplitSample
from training.real_venue_segmentation_v2 import (
    DOOR_ID,
    OUTLET_ID,
    RareClassTrainingDataset,
    _to_tensors,
    boosted_class_weights,
    tile_positions,
    tiled_logits,
)


def _sample(tmp_path: Path, name: str, labels: np.ndarray) -> SplitSample:
    image_path = tmp_path / f"{name}.jpg"
    mask_path = tmp_path / f"{name}.png"
    Image.fromarray(np.full((*labels.shape, 3), 180, dtype=np.uint8), mode="RGB").save(image_path)
    Image.fromarray(labels.astype(np.uint8), mode="L").save(mask_path)
    return SplitSample(name, "train", image_path, mask_path, "", "")


def test_rare_dataset_adds_door_and_outlet_views(tmp_path):
    labels = np.zeros((128, 128), dtype=np.uint8)
    labels[20:80, 20:45] = DOOR_ID
    labels[90:96, 100:106] = OUTLET_ID
    sample = _sample(tmp_path, "scene", labels)
    dataset = RareClassTrainingDataset(
        [sample],
        image_size=64,
        random_crops_per_scene=1,
        door_crops_per_scene=2,
        outlet_crops_per_scene=3,
    )
    assert len(dataset) == 1 + 1 + 2 + 3
    assert dataset.presence == {"door_scenes": 1, "outlet_scenes": 1}
    image, mask, scene_id = dataset[0]
    assert image.shape == (3, 64, 64)
    assert mask.shape == (64, 64)
    assert scene_id == "scene"


def test_boosted_weights_strengthen_rare_classes():
    base = torch.ones(6)
    boosted = boosted_class_weights(base, door_multiplier=2.0, outlet_multiplier=4.0)
    assert boosted[DOOR_ID] > boosted[0]
    assert boosted[OUTLET_ID] > boosted[DOOR_ID]


def test_tile_positions_cover_last_edge():
    positions = tile_positions(512, 256, 192)
    assert positions[0] == 0
    assert positions[-1] == 256


def test_tiled_logits_returns_full_canvas():
    class Tiny(torch.nn.Module):
        def forward(self, x):
            batch, _channels, height, width = x.shape
            return torch.zeros((batch, 6, height, width), dtype=x.dtype, device=x.device)

    image = torch.zeros((1, 3, 512, 512))
    output = tiled_logits(Tiny(), image, tile_size=256, stride=192)
    assert output.shape == (1, 6, 512, 512)


def test_imagenet_normalization_matches_pretrained_encoder_expectation():
    image = Image.new("RGB", (4, 4), (255, 255, 255))
    mask = Image.new("L", (4, 4), 0)
    tensor, _labels = _to_tensors(
        image, mask, "scene", normalization="imagenet"
    )
    expected = torch.tensor(
        [
            (1.0 - 0.485) / 0.229,
            (1.0 - 0.456) / 0.224,
            (1.0 - 0.406) / 0.225,
        ]
    )
    assert torch.allclose(tensor[:, 0, 0], expected, atol=1e-5)
