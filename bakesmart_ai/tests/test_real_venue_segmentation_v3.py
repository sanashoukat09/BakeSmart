import torch

from training.train_real_venue_segmentation_v3 import (
    balanced_class_weights,
    balanced_validation_score,
)


def _metrics(miou: float, door: float, outlet: float) -> dict[str, object]:
    return {
        "mean_iou": miou,
        "per_class": {
            "wall": {"iou": 0.6},
            "floor": {"iou": 0.5},
            "door": {"iou": door},
            "window": {"iou": 0.4},
            "furniture": {"iou": 0.4},
            "outlet": {"iou": outlet},
        },
    }


def test_balanced_validation_score_keeps_miou_dominant():
    stronger_global = balanced_validation_score(_metrics(0.40, 0.00, 0.00))
    weaker_global_with_rare = balanced_validation_score(_metrics(0.30, 0.20, 0.20))
    assert stronger_global > weaker_global_with_rare


def test_balanced_validation_score_rewards_rare_class_improvement():
    base = balanced_validation_score(_metrics(0.35, 0.00, 0.00))
    improved = balanced_validation_score(_metrics(0.35, 0.10, 0.10))
    assert improved > base


def test_balanced_weights_do_not_allow_outlet_to_dominate_extremely():
    base = torch.tensor([0.25, 0.28, 1.27, 0.45, 0.25, 3.60])
    weights = balanced_class_weights(base)
    assert float(weights[5]) <= 4.0
    assert float(weights[2]) < float(weights[5])
    assert float(weights[5]) < 5.0


def test_balanced_weights_reject_invalid_multiplier():
    base = torch.ones(6)
    try:
        balanced_class_weights(base, outlet_multiplier=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected invalid multiplier to be rejected")
