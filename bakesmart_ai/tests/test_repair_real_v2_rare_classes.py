from __future__ import annotations

import numpy as np

from training.repair_real_v2_rare_classes import repair_mask


def test_unlisted_scene_removes_all_rare_components_without_touching_other_pixels():
    labels = np.zeros((80, 100), dtype=np.uint8)
    labels[40:, :] = 1
    labels[10:35, 10:30] = 2
    labels[45:55, 70:80] = 5
    original = labels.copy()

    repaired, report = repair_mask("real-venue-test", labels)

    assert not np.any(repaired == 2)
    assert not np.any(repaired == 5)
    assert np.array_equal(repaired[~np.isin(original, [2, 5])], original[~np.isin(original, [2, 5])])
    assert report["after"] == {"door_components": 0, "outlet_components": 0}


def test_curated_scene_keeps_door_and_reduces_outlet_blob_to_core():
    labels = np.zeros((120, 120), dtype=np.uint8)
    labels[10:100, 10:40] = 2
    labels[60:100, 70:110] = 5
    outlet_before = int(np.count_nonzero(labels == 5))

    repaired, report = repair_mask("real-venue-0022", labels)

    assert np.any(repaired == 2)
    assert 0 < int(np.count_nonzero(repaired == 5)) < outlet_before
    assert report["after"]["door_components"] == 1
    assert report["after"]["outlet_components"] == 1
