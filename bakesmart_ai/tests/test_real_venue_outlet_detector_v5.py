import numpy as np
import torch

from training.train_real_venue_outlet_detector_v5 import (
    _box_iou,
    _validate_target,
    object_boxes,
    outlet_boxes,
)


def test_outlet_boxes_extract_connected_regions():
    labels = np.zeros((20, 30), dtype=np.uint8)
    labels[2:6, 3:8] = 5
    labels[12:18, 20:27] = 5
    boxes = outlet_boxes(labels)
    assert boxes.tolist() == [[3.0, 2.0, 8.0, 6.0], [20.0, 12.0, 27.0, 18.0]]


def test_box_iou_is_one_for_identical_boxes():
    box = torch.tensor([2.0, 3.0, 10.0, 12.0])
    assert _box_iou(box, box) == 1.0


def test_outlet_boxes_expand_single_pixel_component_only_when_not_noise():
    labels = np.zeros((12, 12), dtype=np.uint8)
    labels[4:6, 5:7] = 5
    boxes = outlet_boxes(labels)
    assert boxes.shape == (1, 4)
    assert boxes[0, 2] - boxes[0, 0] >= 4
    assert boxes[0, 3] - boxes[0, 1] >= 4


def test_target_validation_accepts_empty_negative_scene():
    target = {"boxes": torch.zeros((0, 4), dtype=torch.float32)}
    _validate_target(target, 100, 80, "negative-scene")


def test_generic_box_extraction_supports_door_class():
    labels = np.zeros((30, 40), dtype=np.uint8)
    labels[4:25, 10:22] = 2
    boxes = object_boxes(labels, 2)
    assert boxes.tolist() == [[10.0, 4.0, 22.0, 25.0]]
