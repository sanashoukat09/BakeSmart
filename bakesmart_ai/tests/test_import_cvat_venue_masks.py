import io
import zipfile

import numpy as np
import pytest
from PIL import Image

from training.annotation_workspace import AnnotationWorkspace
from training.import_cvat_venue_masks import (
    CvatVenueMaskImporter,
    decode_cvat_mask,
    parse_labelmap,
)


LABELMAP = """background:0,0,0::
wall:229,115,115::
floor:100,181,246::
door:255,183,77::
window:77,208,225::
furniture:149,117,205::
outlet:240,98,146::
"""


def _workspace(tmp_path):
    images = tmp_path / "data" / "venue_vision" / "raw" / "real_v2" / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (16, 12), (190, 180, 170)).save(images / "real-venue-0001.jpg")
    return AnnotationWorkspace(tmp_path)


def _archive(tmp_path, *, leave_background=False):
    rgb = np.empty((12, 16, 3), dtype=np.uint8)
    rgb[:7] = (229, 115, 115)
    rgb[7:] = (100, 181, 246)
    rgb[8:10, 6:10] = (149, 117, 205)
    rgb[3:7, 1:3] = (255, 183, 77)
    rgb[2:5, 11:14] = (77, 208, 225)
    rgb[5:6, 4:5] = (240, 98, 146)
    if leave_background:
        rgb[0, 0] = (0, 0, 0)
    buffer = io.BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buffer, format="PNG")
    archive_path = tmp_path / "cvat.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("labelmap.txt", LABELMAP)
        archive.writestr("SegmentationClass/real-venue-0001.png", buffer.getvalue())
    return archive_path


def test_import_creates_review_pending_mask_with_derived_walkway(tmp_path):
    workspace = _workspace(tmp_path)
    report = CvatVenueMaskImporter(workspace).import_archive(
        _archive(tmp_path),
        annotator_id="sana-01",
        clearance_pixels=1,
        used_sam=True,
    )
    assert report["validated_scene_count"] == 1
    assert report["complete_pending_review"] == 1
    assert report["annotation_method"] == "cvat_sam_assisted_import"
    with Image.open(workspace.mask_path("real_v2", "real-venue-0001")) as mask:
        values = np.asarray(mask.convert("L"))
    assert 6 in np.unique(values)
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["annotation_method"] == "cvat_sam_assisted_import"
    assert record["walkway_annotation_method"] == "derived_from_floor"
    assert record["training_status"] == "not_for_training"


def test_background_pixels_keep_import_as_draft(tmp_path):
    workspace = _workspace(tmp_path)
    report = CvatVenueMaskImporter(workspace).import_archive(
        _archive(tmp_path, leave_background=True),
        annotator_id="sana-01",
        clearance_pixels=1,
    )
    assert report["draft_in_progress"] == 1
    assert report["annotation_method"] == "cvat_manual_import"
    record = workspace.load_record("real_v2", "real-venue-0001")
    assert record["status"] == "draft_in_progress"


def test_completed_mask_cannot_be_overwritten(tmp_path):
    workspace = _workspace(tmp_path)
    importer = CvatVenueMaskImporter(workspace)
    archive = _archive(tmp_path)
    importer.import_archive(archive, annotator_id="sana-01", clearance_pixels=1)
    with pytest.raises(ValueError, match="already complete"):
        importer.import_archive(
            archive,
            annotator_id="sana-01",
            replace_existing=True,
            clearance_pixels=1,
        )


def test_labelmap_rejects_manual_walkway():
    with pytest.raises(ValueError, match="Do not annotate Walkway"):
        parse_labelmap(LABELMAP + "walkway:1,2,3::\n")


def test_indexed_masks_follow_labelmap_order():
    labelmap = parse_labelmap(LABELMAP)
    indexed = np.ones((3, 4), dtype=np.uint8)
    indexed[2] = 2
    buffer = io.BytesIO()
    Image.fromarray(indexed, mode="L").save(buffer, format="PNG")
    labels, size = decode_cvat_mask(buffer.getvalue(), labelmap)
    assert size == (4, 3)
    assert np.all(labels[:2] == 0)
    assert np.all(labels[2] == 1)
