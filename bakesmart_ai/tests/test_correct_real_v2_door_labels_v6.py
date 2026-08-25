import numpy as np

from training.correct_real_v2_door_labels_v6 import correct_labels


def test_correct_labels_changes_only_door_to_window():
    labels = np.asarray([[0, 2, 3], [5, 2, 1]], dtype=np.uint8)

    corrected, changed = correct_labels(labels)

    assert changed == 2
    assert corrected.tolist() == [[0, 3, 3], [5, 3, 1]]
    assert labels.tolist() == [[0, 2, 3], [5, 2, 1]]
