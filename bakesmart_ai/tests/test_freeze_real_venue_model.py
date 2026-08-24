import argparse

import pytest

from training.evaluate_locked_real_venue_model import evaluate_locked_test
from training.freeze_real_venue_model import (
    choose_best_result,
    validate_rare_class_audit,
)


def _manifest():
    return {
        "scenes": [
            {"scene_id": "train-a", "split": "train", "class_ids_present": [0, 1, 2]},
            {"scene_id": "val-a", "split": "validation", "class_ids_present": [0, 1, 5]},
            {"scene_id": "test-a", "split": "test", "class_ids_present": [0, 1, 2, 5]},
        ]
    }


def test_rare_class_audit_requires_every_train_validation_decision():
    audit = {
        "test_split_used": False,
        "scenes": {"train-a": {"decision": "looks_correct"}},
    }
    with pytest.raises(ValueError, match="not complete"):
        validate_rare_class_audit(_manifest(), audit)


def test_rare_class_audit_accepts_only_complete_non_test_review():
    audit = {
        "test_split_used": False,
        "scenes": {
            "train-a": {"decision": "looks_correct"},
            "val-a": {"decision": "looks_correct"},
        },
    }
    summary = validate_rare_class_audit(_manifest(), audit)
    assert summary == {
        "total": 2,
        "looks_correct": 2,
        "pending": 0,
        "label_issue": 0,
        "unsure": 0,
    }


def test_rare_class_audit_rejects_locked_test_decision():
    audit = {
        "test_split_used": False,
        "scenes": {
            "train-a": {"decision": "looks_correct"},
            "val-a": {"decision": "looks_correct"},
            "test-a": {"decision": "looks_correct"},
        },
    }
    with pytest.raises(ValueError, match="locked-test"):
        validate_rare_class_audit(_manifest(), audit)


def test_best_model_selection_uses_balanced_score_then_miou():
    results = [
        {
            "variant": "v1",
            "balanced_validation_score": 0.50,
            "metrics": {"mean_iou": 0.55},
        },
        {
            "variant": "v3",
            "balanced_validation_score": 0.52,
            "metrics": {"mean_iou": 0.51},
        },
    ]
    assert choose_best_result(results)["variant"] == "v3"


def test_locked_test_requires_exact_acknowledgement(tmp_path):
    args = argparse.Namespace(
        acknowledge_locked_test=None,
        selected_dir=str(tmp_path),
        manifest=str(tmp_path / "missing.json"),
        device="cpu",
    )
    with pytest.raises(ValueError, match="acknowledgement"):
        evaluate_locked_test(args)
