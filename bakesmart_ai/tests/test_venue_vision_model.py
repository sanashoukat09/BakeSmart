import csv
import json

import numpy as np

from training.train_venue_vision import DEFAULT_VENUE_MODEL_DIR
from training.venue_vision_data import (
    DEFAULT_VENUE_DATA_DIR,
    REAL_ANNOTATION_COLUMNS,
    VENUE_LABELS,
    build_index_records,
    load_index,
    render_synthetic_scene,
)
from training.venue_vision_runtime import VenueVisionRuntime


def test_venue_scene_index_is_deterministic_and_leakage_safe():
    records = load_index()
    repeated = build_index_records()

    assert records == repeated
    assert len(records) == 240
    assert sum(record.split == "train" for record in records) == 168
    assert sum(record.split == "validation" for record in records) == 36
    assert sum(record.split == "test" for record in records) == 36
    split_ids = {
        split: {record.scene_id for record in records if record.split == split}
        for split in ("train", "validation", "test")
    }
    assert split_ids["train"].isdisjoint(split_ids["validation"])
    assert split_ids["train"].isdisjoint(split_ids["test"])
    assert split_ids["validation"].isdisjoint(split_ids["test"])


def test_synthetic_scene_has_every_locked_mask_label():
    image, mask = render_synthetic_scene(1420940)
    repeated_image, repeated_mask = render_synthetic_scene(1420940)

    assert image.shape == (48, 48, 3)
    assert mask.shape == (48, 48)
    assert set(np.unique(mask)) == set(range(len(VENUE_LABELS)))
    assert np.array_equal(image, repeated_image)
    assert np.array_equal(mask, repeated_mask)


def test_real_annotation_template_has_rights_and_review_fields():
    path = DEFAULT_VENUE_DATA_DIR / "real_annotations_template.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows == [list(REAL_ANNOTATION_COLUMNS)]
    assert "consent_or_rights_confirmed" in rows[0]
    assert "reviewer_id" in rows[0]
    report = json.loads(
        (DEFAULT_VENUE_DATA_DIR / "dataset_report.json").read_text(encoding="utf-8")
    )
    assert report["real_annotation_rows"] == 0
    assert report["training_gate"]["synthetic_bootstrap_ready"] is True
    assert report["training_gate"]["real_photo_training_ready"] is False


def test_checkpoint_is_from_scratch_and_not_production_approved():
    metadata = json.loads(
        (DEFAULT_VENUE_MODEL_DIR / "model_metadata.json").read_text(encoding="utf-8")
    )
    evaluation = json.loads(
        (DEFAULT_VENUE_MODEL_DIR / "evaluation_report.json").read_text(encoding="utf-8")
    )

    assert metadata["model_version"] == "venue-vision-bootstrap-v1"
    assert metadata["pretrained_weights_used"] is False
    assert metadata["external_ai_api_used"] is False
    assert metadata["production_approved"] is False
    assert metadata["data"]["real_annotation_rows"] == 0
    assert metadata["training"]["test_pixels_rendered_after_model_selection"] is True
    assert evaluation["evaluation_order"] == [
        "validation",
        "locked_test_after_model_selection",
    ]
    assert evaluation["validation"]["macro_iou"] > 0.70
    assert evaluation["test"]["macro_iou"] > 0.70


def test_runtime_candidates_are_capped_and_reproducible():
    runtime = VenueVisionRuntime.load()
    image, _ = render_synthetic_scene(1420940)

    first = runtime.candidates(image)
    second = runtime.candidates(image)

    assert first == second
    assert first
    assert all(candidate.label in VENUE_LABELS for candidate in first)
    assert all(0 <= candidate.confidence < 0.5 for candidate in first)
    assert all(len(candidate.bounding_box) == 4 for candidate in first)
