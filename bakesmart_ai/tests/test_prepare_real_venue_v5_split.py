from __future__ import annotations

import json
from pathlib import Path

import pytest

from training.prepare_real_venue_v5_split import V5SplitError, build_v5_split


def _row(index: int, split: str, classes: list[int]) -> dict[str, object]:
    scene_id = f"real-venue-{index:04d}"
    return {
        "scene_id": scene_id,
        "split": split,
        "image_path": f"images/{scene_id}.jpg",
        "mask_path": f"masks/{scene_id}.png",
        "walkway_mask_path": f"walkways/{scene_id}.png",
        "image_sha256": f"image-{index}",
        "mask_sha256": f"mask-{index}",
        "walkway_sha256": f"walkway-{index}",
        "class_ids_present": classes,
    }


def _manifest(
    tmp_path: Path,
    *,
    outlet_scenes: int = 4,
) -> tuple[Path, list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    for index in range(1, 52):
        classes = [0, 1, 3, 4]
        if index <= 10:
            classes.append(2)
        if index <= outlet_scenes:
            classes.append(5)
        rows.append(_row(index, "train" if index <= 42 else "validation", classes))
    test_rows = [_row(index, "test", [0, 1, 4]) for index in range(52, 61)]
    rows.extend(test_rows)
    payload = {
        "dataset": "real_v2_repaired",
        "test_set_locked": True,
        "test_rows_reused_verbatim": True,
        "test_split_used": False,
        "semantic_class_ids": [0, 1, 2, 3, 4, 5],
        "counts": {"train": 42, "validation": 9, "test": 9},
        "scenes": rows,
    }
    path = tmp_path / "data/venue_vision/raw/real_v2_repaired/splits/split_manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, test_rows


def test_v5_rebalances_only_development_and_preserves_test_rows(tmp_path: Path) -> None:
    source, original_test_rows = _manifest(tmp_path)
    output = source.with_name("v5_split_manifest.json")

    manifest = build_v5_split(source, output, project_dir=tmp_path)

    assert manifest["counts"] == {"train": 42, "validation": 9, "test": 9}
    assert manifest["test_split_used"] is False
    assert manifest["development_membership_rebalanced"] is True
    test_rows = [row for row in manifest["scenes"] if row["split"] == "test"]
    assert test_rows == original_test_rows
    validation = [row for row in manifest["scenes"] if row["split"] == "validation"]
    assert sum(2 in row["class_ids_present"] for row in validation) >= 2
    assert sum(5 in row["class_ids_present"] for row in validation) == 1
    training = [row for row in manifest["scenes"] if row["split"] == "train"]
    assert sum(5 in row["class_ids_present"] for row in training) == 3


def test_v5_rejects_too_few_outlet_scenes(tmp_path: Path) -> None:
    source, _test_rows = _manifest(tmp_path, outlet_scenes=1)
    with pytest.raises(V5SplitError, match="at least two development Outlet"):
        build_v5_split(source, source.with_name("v5.json"), project_dir=tmp_path)
