import json

import numpy as np
from PIL import Image

from training.finalize_real_venue_annotations import RealVenueAnnotationFinalizer
from training.semantic_annotation_workspace import SemanticAnnotationWorkspace


def _workspace(tmp_path):
    root = tmp_path / "data" / "venue_vision" / "raw" / "real_v2"
    images = root / "images"
    masks = root / "masks"
    records = root / "annotation_records"
    images.mkdir(parents=True)
    masks.mkdir(parents=True)
    records.mkdir(parents=True)
    Image.new("RGB", (12, 10), (180, 170, 160)).save(images / "real-venue-0001.jpg")
    return SemanticAnnotationWorkspace(tmp_path)


def _write_completed_record(workspace, scene_id="real-venue-0001"):
    path = workspace.record_path("real_v2", scene_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dataset": "real_v2",
                "scene_id": scene_id,
                "annotator_id": "sana-01",
                "status": "annotation_complete_pending_review",
                "training_status": "not_for_training",
            }
        ),
        encoding="utf-8",
    )


def test_clean_six_class_mask_gets_separate_walkway(tmp_path):
    workspace = _workspace(tmp_path)
    labels = np.zeros((10, 12), dtype=np.uint8)
    labels[5:, :] = 1
    labels[6:9, 4:8] = 4
    Image.fromarray(labels, mode="L").save(workspace.mask_path("real_v2", "real-venue-0001"))
    _write_completed_record(workspace)

    report = RealVenueAnnotationFinalizer(workspace).run()

    assert report["summary"]["all_ready_for_independent_review"] is True
    assert report["summary"]["legacy_class6_masks"] == 0
    walkway_path = workspace.walkway_path("real_v2", "real-venue-0001")
    assert walkway_path.is_file()
    with Image.open(walkway_path) as image:
        walkway = np.asarray(image.convert("L"))
    assert set(np.unique(walkway)).issubset({0, 1})
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["semantic_schema_version"] == 2
    assert record["semantic_class_ids"] == list(range(6))
    assert record["finalization_status"] == "ready_for_independent_review"
    assert record["training_status"] == "not_for_training"


def test_legacy_class6_mask_is_backed_up_and_migrated(tmp_path):
    workspace = _workspace(tmp_path)
    labels = np.zeros((10, 12), dtype=np.uint8)
    labels[5:, :] = 1
    labels[6:9, 2:10] = 6
    Image.fromarray(labels, mode="L").save(workspace.mask_path("real_v2", "real-venue-0001"))
    _write_completed_record(workspace)

    report = RealVenueAnnotationFinalizer(workspace).run()

    assert report["summary"]["legacy_class6_masks"] == 1
    assert report["summary"]["legacy_class6_masks_migrated_or_planned"] == 1
    scene = report["scenes"][0]
    assert scene["migrated_legacy_walkway"] is True
    assert len(scene["backup_paths"]) == 2
    for relative in scene["backup_paths"]:
        assert (tmp_path / relative).is_file()
    with Image.open(workspace.mask_path("real_v2", "real-venue-0001")) as image:
        migrated = np.asarray(image.convert("L"))
    assert 6 not in np.unique(migrated)
    assert np.all(migrated[6:9, 2:10] == 1)
    assert workspace.walkway_path("real_v2", "real-venue-0001").is_file()


def test_unlabelled_completed_mask_is_not_ready(tmp_path):
    workspace = _workspace(tmp_path)
    labels = np.ones((10, 12), dtype=np.uint8)
    labels[0, 0] = 255
    Image.fromarray(labels, mode="L").save(workspace.mask_path("real_v2", "real-venue-0001"))
    _write_completed_record(workspace)

    report = RealVenueAnnotationFinalizer(workspace).run(dry_run=True)

    assert report["summary"]["all_ready_for_independent_review"] is False
    assert report["summary"]["masks_with_unlabelled_pixels"] == 1
    assert report["summary"]["needs_attention"] == 1


def test_wrong_annotation_status_is_not_ready(tmp_path):
    workspace = _workspace(tmp_path)
    labels = np.ones((10, 12), dtype=np.uint8)
    Image.fromarray(labels, mode="L").save(workspace.mask_path("real_v2", "real-venue-0001"))
    record_path = workspace.record_path("real_v2", "real-venue-0001")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps({"status": "draft_in_progress", "annotator_id": "sana-01"}),
        encoding="utf-8",
    )

    report = RealVenueAnnotationFinalizer(workspace).run(dry_run=True)

    assert report["summary"]["wrong_completion_status"] == 1
    assert report["summary"]["all_ready_for_independent_review"] is False
