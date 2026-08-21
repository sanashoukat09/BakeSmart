import numpy as np
import pytest

from training.walkway_generator import derive_walkway_candidate


def test_walkway_is_separate_and_floor_is_preserved():
    labels = np.full((20, 20), 1, dtype=np.uint8)
    labels[8:12, 8:12] = 4
    result = derive_walkway_candidate(labels, clearance_pixels=2)
    assert result.walkway_pixels > 0
    assert result.walkway_components >= 1
    assert np.all(result.semantic_labels[labels == 1] == 1)
    assert np.all(result.semantic_labels[8:12, 8:12] == 4)
    assert set(np.unique(result.walkway_mask)).issubset({0, 1})
    assert np.all(result.walkway_mask[8:12, 8:12] == 0)


def test_legacy_class_six_is_restored_to_floor_without_rewriting_walkway_into_semantics():
    labels = np.full((12, 12), 1, dtype=np.uint8)
    labels[1:11, 1:11] = 6
    result = derive_walkway_candidate(labels, clearance_pixels=1)
    assert 6 not in np.unique(result.semantic_labels)
    assert np.all(result.semantic_labels == 1)
    assert result.walkway_pixels > 0


def test_unlabelled_and_obstacles_are_preserved():
    labels = np.full((10, 10), 1, dtype=np.uint8)
    labels[0, :] = 255
    labels[4:6, 4:6] = 5
    result = derive_walkway_candidate(labels, clearance_pixels=1)
    assert np.all(result.semantic_labels[0, :] == 255)
    assert np.all(result.semantic_labels[4:6, 4:6] == 5)
    assert np.all(result.walkway_mask[4:6, 4:6] == 0)


def test_invalid_ids_are_rejected():
    labels = np.full((8, 8), 9, dtype=np.uint8)
    with pytest.raises(ValueError, match="invalid label IDs"):
        derive_walkway_candidate(labels)
