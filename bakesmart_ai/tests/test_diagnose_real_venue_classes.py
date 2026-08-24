from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from training.diagnose_real_venue_classes import (
    build_findings,
    class_counts,
    component_stats,
)
from training.real_venue_segmentation import CLASS_NAMES, samples_for_split


def test_class_counts_reports_all_six_classes():
    mask = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.uint8)
    counts = class_counts(mask)
    assert set(counts) == set(CLASS_NAMES)
    assert all(counts[name] == 1 for name in CLASS_NAMES)


def test_component_stats_reports_fragmentation():
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[1:3, 1:3] = 5
    mask[7:9, 7:10] = 5
    stats = component_stats(mask, 5)
    assert stats["components"] == 2
    assert stats["largest_component_pixels"] == 6


def test_step4_data_api_refuses_locked_test_split():
    manifest = {"scenes": []}
    with pytest.raises(ValueError, match="locked test split"):
        samples_for_split(manifest, "test", project_dir=Path("."), verify_hashes=False)


def test_findings_distinguish_never_predicted_rare_class():
    split_summary = {
        "validation": {
            "classes": {
                "door": {
                    "scenes_present_raw": 2,
                    "raw_present_but_lost_at_256": 0,
                    "raw_present_but_lost_at_512": 0,
                },
                "outlet": {
                    "scenes_present_raw": 3,
                    "raw_present_but_lost_at_256": 1,
                    "raw_present_but_lost_at_512": 0,
                },
            }
        }
    }
    model_summary = {
        "class_behavior": {
            "door": {
                "interpretation": "never_predicted",
                "ground_truth_pixels": 100,
                "predicted_pixels": 0,
                "iou": 0.0,
            },
            "outlet": {
                "interpretation": "predicted_but_no_overlap",
                "ground_truth_pixels": 20,
                "predicted_pixels": 15,
                "iou": 0.0,
            },
        }
    }
    findings = build_findings(split_summary, model_summary)
    text = "\n".join(findings)
    assert "door: survives 256x256" in text
    assert "outlet: present in 3 validation scenes, but disappears" in text
    assert "v1 door: never_predicted" in text
    assert "v1 outlet: predicted_but_no_overlap" in text
