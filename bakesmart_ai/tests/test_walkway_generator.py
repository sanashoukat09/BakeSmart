import numpy as np
import pytest

from training.walkway_generator import derive_walkway_candidate


def test_walkway_is_derived_only_from_interior_floor():
    labels = np.full((20, 20), 1, dtype=np.uint8)
    labels[8:12, 8:12] = 4
    result = derive_walkway_candidate(labels, clearance_pixels=2)
    assert result.walkway_pixels > 0
    assert result.walkway_components >= 1
    assert np.all(result.labels[8:12, 8:12] == 4)
    assert result.labels[0, 0] == 1
    assert result.labels[7, 7] == 1


def test_existing_walkway_is_reset_before_regeneration():
    labels = np.full((12, 12), 1, dtype=np.uint8)
    labels[1:11, 1:11] = 6
    first = derive_walkway_candidate(labels, clearance_pixels=1)
    second = derive_walkway_candidate(first.labels, clearance_pixels=1)
    assert np.array_equal(first.labels, second.labels)


def test_unlabelled_and_obstacles_are_preserved():
    labels = np.full((10, 10), 1, dtype=np.uint8)
    labels[0, :] = 255
    labels[4:6, 4:6] = 5
    result = derive_walkway_candidate(labels, clearance_pixels=1)
    assert np.all(result.labels[0, :] == 255)
    assert np.all(result.labels[4:6, 4:6] == 5)


def test_invalid_ids_are_rejected():
    labels = np.full((8, 8), 9, dtype=np.uint8)
    with pytest.raises(ValueError, match="invalid label IDs"):
        derive_walkway_candidate(labels)
