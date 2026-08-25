import numpy as np
import torch

from training.train_real_venue_outlet_detector_v5 import _box_iou, outlet_boxes


def test_outlet_boxes_extract_connected_regions():
    labels = np.zeros((20, 30), dtype=np.uint8)
    labels[2:6, 3:8] = 5
    labels[12:18, 20:27] = 5
    boxes = outlet_boxes(labels)
    assert boxes.tolist() == [[3.0, 2.0, 8.0, 6.0], [20.0, 12.0, 27.0, 18.0]]


def test_box_iou_is_one_for_identical_boxes():
    box = torch.tensor([2.0, 3.0, 10.0, 12.0])
    assert _box_iou(box, box) == 1.0
