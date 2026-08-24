import json
from pathlib import Path

import numpy as np
from PIL import Image

from training.rare_class_audit_workspace import RareClassAuditWorkspace


def _write_rgb(path: Path, size=(16, 16)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (120, 120, 120)).save(path)


def _write_mask(path: Path, *, door=False, outlet=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = np.zeros((16, 16), dtype=np.uint8)
    labels[8:, :] = 1
    if door:
        labels[3:12, 2:5] = 2
    if outlet:
        labels[7:9, 12:14] = 5
    Image.fromarray(labels).save(path)


def _manifest(tmp_path: Path):
    rows = []
    for split, scene_id, door, outlet in [
        ("train", "train-a", True, True),
        ("validation", "val-a", True, True),
        ("test", "test-a", True, True),
    ]:
        image = tmp_path / "data" / f"{scene_id}.png"
        mask = tmp_path / "data" / f"{scene_id}-mask.png"
        _write_rgb(image)
        _write_mask(mask, door=door, outlet=outlet)
        import hashlib

        def sha(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()

        rows.append(
            {
                "scene_id": scene_id,
                "split": split,
                "image_path": str(image.relative_to(tmp_path)).replace("\\", "/"),
                "mask_path": str(mask.relative_to(tmp_path)).replace("\\", "/"),
                "image_sha256": sha(image),
                "mask_sha256": sha(mask),
            }
        )
    manifest = {
        "dataset": "real_v2",
        "test_set_locked": True,
        "semantic_class_ids": [0, 1, 2, 3, 4, 5],
        "counts": {"train": 1, "validation": 1, "test": 1},
        "scenes": rows,
    }
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, rows


def test_audit_exposes_only_train_and_validation(tmp_path):
    manifest_path, _rows = _manifest(tmp_path)
    workspace = RareClassAuditWorkspace(
        project_dir=tmp_path,
        manifest_path=manifest_path,
        audit_state_path=tmp_path / "audit.json",
    )
    scene_ids = {scene["scene_id"] for scene in workspace.list_scenes()}
    assert scene_ids == {"train-a", "val-a"}
    assert "test-a" not in workspace.samples


def test_audit_decision_does_not_modify_mask(tmp_path):
    manifest_path, rows = _manifest(tmp_path)
    workspace = RareClassAuditWorkspace(
        project_dir=tmp_path,
        manifest_path=manifest_path,
        audit_state_path=tmp_path / "audit.json",
    )
    train_row = next(row for row in rows if row["scene_id"] == "train-a")
    mask_path = tmp_path / train_row["mask_path"]
    before = mask_path.read_bytes()
    result = workspace.save_decision("train-a", "looks_correct", "checked")
    after = mask_path.read_bytes()
    assert before == after
    assert result["decision"] == "looks_correct"


def test_label_issue_requires_notes(tmp_path):
    import pytest

    manifest_path, _rows = _manifest(tmp_path)
    workspace = RareClassAuditWorkspace(
        project_dir=tmp_path,
        manifest_path=manifest_path,
        audit_state_path=tmp_path / "audit.json",
    )
    with pytest.raises(ValueError, match="notes are required"):
        workspace.save_decision("train-a", "label_issue", "")
