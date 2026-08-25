from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from training.prepare_repaired_real_venue_dataset import (
    RepairedDatasetError,
    _sha256,
    prepare_repaired_dataset,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_repaired_scene(root: Path, scene_id: str, *, rare: bool) -> None:
    image_path = root / "images" / f"{scene_id}.jpg"
    mask_path = root / "masks" / f"{scene_id}.png"
    walkway_path = root / "walkway_masks" / f"{scene_id}.png"
    record_path = root / "annotation_records" / f"{scene_id}.json"
    for path in (image_path, mask_path, walkway_path, record_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((10, 12, 3), dtype=np.uint8)
    image[..., 0] = int(scene_id[-1]) * 20
    Image.fromarray(image).save(image_path)
    labels = np.zeros((10, 12), dtype=np.uint8)
    labels[5:] = 1
    if rare:
        labels[2:7, 4:7] = 2
    Image.fromarray(labels).save(mask_path)
    walkway = np.zeros((10, 12), dtype=np.uint8)
    walkway[7:, 3:9] = 1
    Image.fromarray(walkway).save(walkway_path)
    _write_json(
        record_path,
        {
            "scene_id": scene_id,
            "annotator_id": "a",
            "reviewer_id": "r",
            "review_completed_at": "2026-08-25T00:00:00+00:00",
            "mask_sha256": _sha256(mask_path),
            "walkway_mask_sha256": _sha256(walkway_path),
        },
    )


def _fixture(tmp_path: Path, decision: str = "looks_correct") -> tuple[Path, Path]:
    repaired = tmp_path / "data/venue_vision/raw/real_v2_repaired"
    _make_repaired_scene(repaired, "real-venue-0001", rare=True)
    _make_repaired_scene(repaired, "real-venue-0002", rare=False)
    source_path = tmp_path / "data/venue_vision/raw/real_v2/splits/split_manifest.json"
    test_row = {
        "scene_id": "real-venue-0003",
        "split": "test",
        "image_path": "data/venue_vision/raw/real_v2/images/real-venue-0003.jpg",
        "mask_path": "data/venue_vision/raw/real_v2/masks/real-venue-0003.png",
        "walkway_mask_path": "data/venue_vision/raw/real_v2/walkway_masks/real-venue-0003.png",
        "image_sha256": "locked-image-hash",
        "mask_sha256": "locked-mask-hash",
        "walkway_sha256": "locked-walkway-hash",
        "class_ids_present": [0, 1],
    }
    _write_json(
        source_path,
        {
            "dataset": "real_v2",
            "test_set_locked": True,
            "counts": {"train": 1, "validation": 1, "test": 1},
            "semantic_classes": ["wall", "floor", "door", "window", "furniture", "outlet"],
            "scenes": [
                {"scene_id": "real-venue-0001", "split": "train"},
                {"scene_id": "real-venue-0002", "split": "validation"},
                test_row,
            ],
        },
    )
    _write_json(
        repaired / "diagnostics/rare_class_visual_audit.json",
        {
            "dataset": "real_v2_repaired",
            "test_split_used": False,
            "scenes": {"real-venue-0001": {"decision": decision}},
        },
    )
    return source_path, repaired


def test_prepare_preserves_test_row_without_test_files(tmp_path: Path) -> None:
    source_path, repaired = _fixture(tmp_path)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    original_test = source["scenes"][2]

    manifest = prepare_repaired_dataset(source_path, repaired, project_dir=tmp_path)

    assert manifest["dataset"] == "real_v2_repaired"
    assert manifest["test_split_used"] is False
    assert manifest["test_rows_reused_verbatim"] is True
    assert manifest["scenes"][2] == original_test
    assert "real_v2_repaired" in manifest["scenes"][0]["mask_path"]
    assert (repaired / "splits/split_manifest.json").is_file()
    train_record = json.loads(
        (repaired / "annotation_records/real-venue-0001.json").read_text(encoding="utf-8")
    )
    assert train_record["training_status"] == "approved_for_training"


def test_prepare_rejects_unresolved_rare_class_audit(tmp_path: Path) -> None:
    source_path, repaired = _fixture(tmp_path, decision="label_issue")
    with pytest.raises(RepairedDatasetError, match="still need approval"):
        prepare_repaired_dataset(source_path, repaired, project_dir=tmp_path)


def test_prepare_rejects_test_scene_in_audit(tmp_path: Path) -> None:
    source_path, repaired = _fixture(tmp_path)
    audit_path = repaired / "diagnostics/rare_class_visual_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["scenes"]["real-venue-0003"] = {"decision": "looks_correct"}
    _write_json(audit_path, audit)
    with pytest.raises(RepairedDatasetError, match="locked-test or unknown"):
        prepare_repaired_dataset(source_path, repaired, project_dir=tmp_path)
