import json

import numpy as np
import pytest
from PIL import Image

from training.semantic_annotation_workspace import SemanticAnnotationWorkspace
from training.venue_review_workspace import VenueReviewWorkspace


def _setup(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    masks = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "masks"
    records = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "annotation_records"
    images.mkdir(parents=True)
    masks.mkdir(parents=True)
    records.mkdir(parents=True)
    Image.new("RGB", (12, 8), (190, 180, 170)).save(images / "real-venue-0001.jpg")
    labels = np.ones((8, 12), dtype=np.uint8)
    labels[:4] = 0
    Image.fromarray(labels).save(masks / "real-venue-0001.png")
    workspace = SemanticAnnotationWorkspace(tmp_path)
    record = workspace._record(
        dataset_key="real_v2",
        scene_id="real-venue-0001",
        annotator_id="sana-01",
        status="annotation_complete_pending_review",
        annotation_completed_at=workspace._utc_now(),
    )
    workspace._write_record("real_v2", "real-venue-0001", record)
    before = (masks / "real-venue-0001.png").read_bytes()
    return workspace, VenueReviewWorkspace(tmp_path, workspace), before


def test_reviewer_must_be_different_from_annotator(tmp_path):
    _, review, _ = _setup(tmp_path)
    with pytest.raises(ValueError, match="different from the annotator"):
        review.submit_review(
            dataset_key="real_v2",
            scene_id="real-venue-0001",
            reviewer_id="sana-01",
            decision="approved",
        )


def test_correction_requires_notes(tmp_path):
    _, review, _ = _setup(tmp_path)
    with pytest.raises(ValueError, match="notes are required"):
        review.submit_review(
            dataset_key="real_v2",
            scene_id="real-venue-0001",
            reviewer_id="reviewer-02",
            decision="needs_correction",
        )


def test_approval_updates_metadata_without_changing_mask(tmp_path):
    workspace, review, mask_before = _setup(tmp_path)
    result = review.submit_review(
        dataset_key="real_v2",
        scene_id="real-venue-0001",
        reviewer_id="reviewer-02",
        decision="approved",
        notes="Looks correct.",
    )
    assert result["review_status"] == "approved"
    assert result["training_status"] == "approved_pending_split"
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["reviewer_id"] == "reviewer-02"
    assert record["review_status"] == "approved"
    assert record["training_status"] == "approved_pending_split"
    assert workspace.mask_path("real_v2", "real-venue-0001").read_bytes() == mask_before


def test_summary_counts_review_decisions(tmp_path):
    _, review, _ = _setup(tmp_path)
    before = review.summary().as_dict()
    assert before["pending"] == 1
    review.submit_review(
        dataset_key="real_v2",
        scene_id="real-venue-0001",
        reviewer_id="reviewer-02",
        decision="rejected",
        notes="Mask quality is not usable.",
    )
    after = review.summary().as_dict()
    assert after["pending"] == 0
    assert after["rejected"] == 1
