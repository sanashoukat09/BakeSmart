from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from training.semantic_annotation_workspace import SemanticAnnotationWorkspace
from training.split_real_venue_dataset import (
    RealVenueDatasetSplitter,
    SplitError,
    _allocate_counts,
)


def _make_scene(
    root: Path,
    scene_id: str,
    *,
    review_status: str = "approved",
    training_status: str = "approved_pending_split",
    class_ids: tuple[int, ...] = (0, 1, 4),
) -> None:
    images = root / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    masks = root / "data" / "venue_vision" / "raw" / "real_v2" / "masks"
    walkways = root / "data" / "venue_vision" / "raw" / "real_v2" / "walkway_masks"
    records = root / "data" / "venue_vision" / "raw" / "real_v2" / "annotation_records"
    for path in (images, masks, walkways, records):
        path.mkdir(parents=True, exist_ok=True)

    number = int(scene_id.rsplit("-", 1)[1])
    image = np.zeros((12, 16, 3), dtype=np.uint8)
    image[..., 0] = number % 251
    image[..., 1] = (number * 3) % 251
    Image.fromarray(image).save(images / f"{scene_id}.jpg", quality=95)

    labels = np.full((12, 16), class_ids[0], dtype=np.uint8)
    stripe = max(1, labels.shape[1] // len(class_ids))
    for index, class_id in enumerate(class_ids):
        start = index * stripe
        end = labels.shape[1] if index + 1 == len(class_ids) else (index + 1) * stripe
        labels[:, start:end] = class_id
    Image.fromarray(labels).save(masks / f"{scene_id}.png")

    walkway = np.zeros((12, 16), dtype=np.uint8)
    walkway[8:, 3:13] = 1
    Image.fromarray(walkway).save(walkways / f"{scene_id}.png")

    record = {
        "dataset": "real_v2",
        "scene_id": scene_id,
        "annotator_id": "annotator-01",
        "status": "annotation_complete_pending_review",
        "reviewer_id": "reviewer-01" if review_status == "approved" else "reviewer-02",
        "review_status": review_status,
        "review_completed_at": "2026-08-23T10:00:00+00:00",
        "training_status": training_status,
    }
    (records / f"{scene_id}.json").write_text(json.dumps(record), encoding="utf-8")


def _workspace(tmp_path: Path) -> SemanticAnnotationWorkspace:
    return SemanticAnnotationWorkspace(project_dir=tmp_path)


def test_allocate_sixty_is_42_9_9() -> None:
    assert _allocate_counts(60) == {"train": 42, "validation": 9, "test": 9}


def test_split_sixty_approved_is_locked_and_disjoint(tmp_path: Path) -> None:
    for index in range(1, 61):
        classes = (0, 1, 4)
        if index % 2 == 0:
            classes += (3,)
        if index % 3 == 0:
            classes += (2,)
        if index % 5 == 0:
            classes += (5,)
        _make_scene(tmp_path, f"real-venue-{index:04d}", class_ids=classes)

    splitter = RealVenueDatasetSplitter(_workspace(tmp_path))
    manifest = splitter.run(seed=12345)

    assert manifest["counts"] == {"train": 42, "validation": 9, "test": 9}
    assert manifest["test_set_locked"] is True
    rows = manifest["scenes"]
    assert len(rows) == 60
    assert len({row["scene_id"] for row in rows}) == 60
    assert {row["split"] for row in rows} == {"train", "validation", "test"}

    split_dir = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "splits"
    assert (split_dir / "split_manifest.json").is_file()
    assert (split_dir / "split_manifest.csv").is_file()

    workspace = _workspace(tmp_path)
    for row in rows:
        record = workspace.load_record("real_v2", row["scene_id"])
        assert record["dataset_split"] == row["split"]
        if row["split"] == "test":
            assert record["training_status"] == "approved_for_locked_test"


def test_rerun_reuses_exact_locked_membership(tmp_path: Path) -> None:
    for index in range(1, 21):
        _make_scene(tmp_path, f"real-venue-{index:04d}", class_ids=(0, 1, 4, index % 3 + 2))

    splitter = RealVenueDatasetSplitter(_workspace(tmp_path))
    first = splitter.run(seed=7)
    first_membership = {
        row["scene_id"]: row["split"] for row in first["scenes"]
    }
    second = splitter.run(seed=99999)
    second_membership = {
        row["scene_id"]: row["split"] for row in second["scenes"]
    }
    assert second_membership == first_membership
    assert second["seed"] == 7


def test_unresolved_review_blocks_split(tmp_path: Path) -> None:
    _make_scene(tmp_path, "real-venue-0001")
    _make_scene(
        tmp_path,
        "real-venue-0002",
        review_status="needs_correction",
        training_status="not_for_training",
    )
    _make_scene(tmp_path, "real-venue-0003")

    with pytest.raises(SplitError, match="Step 2 is not complete"):
        RealVenueDatasetSplitter(_workspace(tmp_path)).run()


def test_rejected_scene_is_excluded(tmp_path: Path) -> None:
    for index in range(1, 11):
        _make_scene(tmp_path, f"real-venue-{index:04d}")
    _make_scene(
        tmp_path,
        "real-venue-0011",
        review_status="rejected",
        training_status="rejected",
    )

    manifest = RealVenueDatasetSplitter(_workspace(tmp_path)).run(seed=3)
    ids = {row["scene_id"] for row in manifest["scenes"]}
    assert "real-venue-0011" not in ids
    assert manifest["approved_scene_count"] == 10
    assert manifest["rejected_scene_count"] == 1


def test_changed_approved_set_does_not_silently_reshuffle(tmp_path: Path) -> None:
    for index in range(1, 11):
        _make_scene(tmp_path, f"real-venue-{index:04d}")
    splitter = RealVenueDatasetSplitter(_workspace(tmp_path))
    splitter.run(seed=5)

    _make_scene(tmp_path, "real-venue-0011")
    with pytest.raises(SplitError, match="approved scene set changed"):
        splitter.run(seed=5)


def test_force_resplit_requires_explicit_test_lock_acknowledgement(tmp_path: Path) -> None:
    for index in range(1, 11):
        _make_scene(tmp_path, f"real-venue-{index:04d}")
    splitter = RealVenueDatasetSplitter(_workspace(tmp_path))
    splitter.run(seed=5)

    with pytest.raises(SplitError, match="acknowledge-test-lock-reset"):
        splitter.run(seed=9, force_resplit=True)
