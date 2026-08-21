import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from training.annotation_workspace import AnnotationWorkspace
from training.mask_suggestion import MaskSuggestionService
from training.venue_labeler import create_app
from training.venue_vision_data import VENUE_LABELS


class _FakeModel:
    def predict_proba(self, features):
        probabilities = np.zeros((features.shape[0], len(VENUE_LABELS)), dtype=np.float64)
        probabilities[:, 1] = 1.0
        return {"segmentation": probabilities}


class _FakeRuntime:
    image_size = 4
    model_version = "fake-venue-v1"
    model = _FakeModel()


def _workspace(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (8, 6), (190, 180, 170)).save(images / "real-venue-0001.jpg")
    return AnnotationWorkspace(tmp_path)


def test_suggestion_creates_machine_assisted_draft_and_provenance(tmp_path):
    workspace = _workspace(tmp_path)
    service = MaskSuggestionService(runtime=_FakeRuntime())

    result = service.suggest(
        workspace=workspace,
        dataset_key="real_v2",
        scene_id="real-venue-0001",
        annotator_id="sana-01",
    )

    assert result["complete"] is True
    assert result["class_counts"]["floor"] == 48
    assert result["status"] == "draft_in_progress"
    assert result["human_review_required"] is True
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["annotation_method"] == "machine_assisted_draft"
    assert record["suggestion_model_version"] == "fake-venue-v1"
    assert record["training_status"] == "not_for_training"
    provenance_path = workspace.record_path(
        "real_v2", "real-venue-0001"
    ).with_name("real-venue-0001.suggestion.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["human_review_required"] is True
    assert provenance["training_status"] == "not_for_training"


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
    assert payload["human_review_required"] is True
