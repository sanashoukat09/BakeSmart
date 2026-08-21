import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from training.annotation_workspace import AnnotationWorkspace, UNLABELLED_ID
from training.mask_suggestion import MaskSuggestionService
from training.venue_labeler import create_app
from training.venue_vision_data import VENUE_LABELS


class _FakeModel:
    def predict_proba(self, features):
        probabilities = np.full(
            (features.shape[0], len(VENUE_LABELS)),
            0.01,
            dtype=np.float64,
        )
        rows = features[:, -1]
        upper = rows < 0
        probabilities[upper, 0] = 0.94
        probabilities[~upper, 1] = 0.94
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        return {"segmentation": probabilities}


class _FakeRuntime:
    image_size = 4
    model_version = "fake-venue-v1"
    model = _FakeModel()


def _workspace(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    pixels = np.zeros((60, 80, 3), dtype=np.uint8)
    pixels[:38] = (205, 195, 185)
    pixels[38:] = (95, 90, 85)
    Image.fromarray(pixels, mode="RGB").save(images / "real-venue-0001.jpg")
    return AnnotationWorkspace(tmp_path)


def test_suggestion_creates_high_resolution_machine_assisted_draft(tmp_path):
    workspace = _workspace(tmp_path)
    service = MaskSuggestionService(runtime=_FakeRuntime())

    result = service.suggest(
        workspace=workspace,
        dataset_key="real_v2",
        scene_id="real-venue-0001",
        annotator_id="sana-01",
    )

    assert result["status"] == "draft_in_progress"
    assert result["human_review_required"] is True
    assert result["suggestion_strategy"] == "high_resolution_conservative_v2"
    assert result["working_size"] == [80, 60]
    assert result["class_counts"]["wall"] > 0
    assert result["class_counts"]["floor"] > 0
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["annotation_method"] == "machine_assisted_draft"
    assert record["suggestion_model_version"] == "fake-venue-v1"
    assert record["suggestion_strategy"] == "high_resolution_conservative_v2"
    assert record["suggestion_working_width"] == 80
    assert record["suggestion_working_height"] == 60
    assert record["training_status"] == "not_for_training"
    provenance_path = workspace.record_path(
        "real_v2", "real-venue-0001"
    ).with_name("real-venue-0001.suggestion.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["schema_version"] == 2
    assert provenance["human_review_required"] is True
    assert provenance["training_status"] == "not_for_training"


def test_conservative_labels_leave_low_confidence_special_class_unlabelled():
    service = MaskSuggestionService(runtime=_FakeRuntime())
    probabilities = np.full((20, 20, len(VENUE_LABELS)), 0.01, dtype=np.float64)
    probabilities[..., 0] = 0.26
    probabilities[4:7, 4:7, 5] = 0.30
    probabilities /= probabilities.sum(axis=2, keepdims=True)
    labels = service._conservative_labels(probabilities, floor_boundary=13)
    assert np.count_nonzero(labels == UNLABELLED_ID) > 0


def test_suggestion_requires_explicit_replacement_of_existing_draft(tmp_path):
    workspace = _workspace(tmp_path)
    service = MaskSuggestionService(runtime=_FakeRuntime())
    service.suggest(
        workspace=workspace,
        dataset_key="real_v2",
        scene_id="real-venue-0001",
    )
    with pytest.raises(ValueError, match="Confirm replacement"):
        service.suggest(
            workspace=workspace,
            dataset_key="real_v2",
            scene_id="real-venue-0001",
        )
    replaced = service.suggest(
        workspace=workspace,
        dataset_key="real_v2",
        scene_id="real-venue-0001",
        replace_existing=True,
    )
    assert replaced["status"] == "draft_in_progress"


def test_suggest_endpoint_returns_draft_mask(tmp_path):
    workspace = _workspace(tmp_path)
    app = create_app(
        workspace=workspace,
        suggestion_service=MaskSuggestionService(runtime=_FakeRuntime()),
        static_dir=None,
    )
    client = TestClient(app)
    response = client.post(
        "/api/scenes/real_v2/real-venue-0001/suggest",
        json={"annotator_id": "sana-01", "replace_existing": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "draft_in_progress"
    assert payload["suggestion_model_version"] == "fake-venue-v1"
    assert payload["suggestion_strategy"] == "high_resolution_conservative_v2"
    assert payload["human_review_required"] is True
