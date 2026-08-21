"""ADE20K-to-BakeSmart label mapping for automatic venue-mask drafts.

The pretrained helper model is used only to accelerate annotation. BakeSmart's
final venue model remains a separate model trained on reviewed BakeSmart masks.
"""

from __future__ import annotations

import numpy as np

from training.annotation_workspace import UNLABELLED_ID


# ADE20K SceneParse150 IDs used by SegFormer. Only categories that have a
# defensible BakeSmart meaning are mapped. Unsupported content (for example sky,
# water and people) stays 255 so the human reviewer can see it immediately.
WALL_ADE_IDS = frozenset({0, 1, 5, 25, 32, 34, 42, 48, 84, 95})
FLOOR_ADE_IDS = frozenset({3, 6, 9, 11, 13, 28, 29, 46, 52, 53, 54, 59, 68, 91, 94, 121, 140})
DOOR_ADE_IDS = frozenset({14, 58})
WINDOW_ADE_IDS = frozenset({8, 63})
FURNITURE_ADE_IDS = frozenset(
    {
        4, 7, 10, 15, 17, 18, 19, 20, 22, 23, 24, 27, 30, 31, 33, 35,
        36, 37, 38, 39, 40, 41, 43, 44, 45, 47, 49, 50, 55, 56, 57, 62,
        64, 65, 66, 67, 69, 70, 71, 72, 73, 74, 75, 77, 78, 81, 82, 83,
        85, 86, 87, 88, 89, 92, 93, 97, 98, 99, 100, 101, 102, 105,
        106, 107, 108, 110, 111, 112, 114, 115, 116, 117, 118, 119,
        120, 122, 123, 124, 125, 126, 127, 129, 130, 131, 132, 133,
        134, 135, 136, 137, 138, 139, 141, 142, 143, 144, 145, 146,
        147, 148, 149,
    }
)

# ADE20K categories intentionally not forced into a BakeSmart class.
# 2 sky, 12 person, 16 mountain, 21 water, 26 sea, 51 grandstand,
# 60 river, 61 bridge, 76 boat, 79 hovel, 80 bus, 90 airplane, 96 escalator,
# 103 ship, 104 fountain, 109 swimming pool, 113 waterfall, 128 lake.


def build_lookup() -> np.ndarray:
    lookup = np.full(150, UNLABELLED_ID, dtype=np.uint8)
    for class_id in WALL_ADE_IDS:
        lookup[class_id] = 0
    for class_id in FLOOR_ADE_IDS:
        lookup[class_id] = 1
    for class_id in DOOR_ADE_IDS:
        lookup[class_id] = 2
    for class_id in WINDOW_ADE_IDS:
        lookup[class_id] = 3
    for class_id in FURNITURE_ADE_IDS:
        lookup[class_id] = 4
    return lookup


ADE_TO_BAKESMART = build_lookup()


def map_ade20k_to_bakesmart(ade_labels: np.ndarray) -> np.ndarray:
    """Map a 2-D ADE20K class-id image to BakeSmart IDs 0-4 or 255."""

    labels = np.asarray(ade_labels)
    if labels.ndim != 2:
        raise ValueError("ADE20K label map must be two-dimensional")
    if labels.size == 0:
        raise ValueError("ADE20K label map must not be empty")
    if int(labels.min()) < 0 or int(labels.max()) >= len(ADE_TO_BAKESMART):
        raise ValueError("ADE20K label map contains class IDs outside 0-149")
    return ADE_TO_BAKESMART[labels.astype(np.int64)]


def mapping_coverage(labels: np.ndarray) -> float:
    values = np.asarray(labels)
    if values.ndim != 2 or values.size == 0:
        raise ValueError("BakeSmart mask must be a non-empty 2-D array")
    return float(np.count_nonzero(values != UNLABELLED_ID) / values.size)
