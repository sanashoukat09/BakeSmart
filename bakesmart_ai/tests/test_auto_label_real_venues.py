import json

import numpy as np
from PIL import Image

from training.auto_label_mapping import map_ade20k_to_bakesmart
from training.auto_label_real_venues import AutoLabelPrediction, BatchVenueAutoLabeller
from training.semantic_annotation_workspace import SemanticAnnotationWorkspace


class _FakeEngine:
    model_version = "fake-helper-v1"

    def predict(self, image):
        width, height = image.size
        labels = np.zeros((height, width), dtype=np.uint8)
        labels[height // 2 :] = 1
        labels[height // 2 - 2 : height // 2 + 2, width // 3 : 2 * width // 3] = 4
        confidence = np.full((height, width), 0.92, dtype=np.float32)
        return AutoLabelPrediction(
            labels=labels,
            pixel_confidence=confidence,
            mean_confidence=0.92,
            direct_mapping_fraction=1.0,
        )


def _workspace(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (32, 24), (180, 170, 160)).save(images / "real-venue-0001.jpg")
    return SemanticAnnotationWorkspace(tmp_path)


def test_ade_mapping_maps_core_room_classes_and_leaves_sky_unlabelled():
    ade = np.asarray([[0, 3, 14, 8, 23, 2]], dtype=np.uint8)
    mapped = map_ade20k_to_bakesmart(ade)
    assert mapped.tolist() == [[0, 1, 2, 3, 4, 255]]


def test_batch_auto_labeller_saves_semantics_and_separate_walkway(tmp_path):
    workspace = _workspace(tmp_path)
    report = BatchVenueAutoLabeller(workspace, _FakeEngine()).run(
        annotator_id="sana-01",
    )
    assert report["auto_labelled_scene_count"] == 1
    assert report["quick_review_count"] == 1
    assert report["semantic_schema"] == "six_visual_classes_v2"
    assert report["walkway_storage"] == "separate_binary_mask"

    with Image.open(workspace.mask_path("real_v2", "real-venue-0001")) as mask:
        semantic = np.asarray(mask.convert("L"))
    assert 6 not in np.unique(semantic)
    assert np.count_nonzero(semantic == 1) > 0

    walkway_path = workspace.walkway_path("real_v2", "real-venue-0001")
    assert walkway_path.is_file()
    with Image.open(walkway_path) as mask:
        walkway = np.asarray(mask.convert("L"))
    assert set(np.unique(walkway)).issubset({0, 1})
    assert np.count_nonzero(walkway) > 0

    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["status"] == "draft_in_progress"
    assert record["annotation_method"] == "pretrained_scene_model_draft"
    assert record["annotation_helper_is_final_model"] is False
    assert record["human_review_required"] is True
    assert record["semantic_class_ids"] == [0, 1, 2, 3, 4, 5]
    assert record["walkway_storage"] == "separate_binary_mask"
    assert record["training_status"] == "not_for_training"

    provenance_path = workspace.record_path(
        "real_v2", "real-venue-0001"
    ).with_name("real-venue-0001.autolabel.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["annotation_helper_model_version"] == "fake-helper-v1"
    assert provenance["human_review_required"] is True


def test_existing_mask_is_skipped_without_replace(tmp_path):
    workspace = _workspace(tmp_path)
    labeller = BatchVenueAutoLabeller(workspace, _FakeEngine())
    first = labeller.run()
    second = labeller.run()
    assert first["auto_labelled_scene_count"] == 1
    assert second["auto_labelled_scene_count"] == 0
    assert second["scenes"][0]["reason"] == "existing_mask_use_--replace-existing"
