import json

import torch

from training.finalize_real_venue_v6_bundle import finalize
from training.real_venue_segmentation import sha256_file


def _write_checkpoint(path, *, model_name, manifest_sha, metrics, config=None):
    path.parent.mkdir(parents=True)
    torch.save(
        {
            "schema_version": 6,
            "model_name": model_name,
            "architecture": "test",
            "num_classes": 2,
            "class_names": ["background", "door"],
            "test_data_used": False,
            "manifest_sha256": manifest_sha,
            "epoch": 6,
            "validation_metrics": metrics,
            "config": config or {},
            "model_state_dict": {"weight": torch.ones(1)},
            "optimizer_state_dict": {"must_not_be_packaged": True},
        },
        path,
    )


def _write_report(path, *, model_name, checkpoint, manifest_sha, metrics, positives=None):
    payload = {
        "model_name": model_name,
        "checkpoint_sha256": sha256_file(checkpoint),
        "split_manifest_sha256": manifest_sha,
        "test_split_used": False,
        "production_ready": False,
        "best_validation_metrics": metrics,
    }
    if positives is not None:
        payload["validation_positive_scene_count"] = positives
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_finalize_creates_validation_only_bundle_without_optimizer(tmp_path):
    segmentation_dir = tmp_path / "segmentation"
    door_dir = tmp_path / "door"
    output_dir = tmp_path / "bundle"
    segmentation_metrics = {"mean_iou": 0.3987, "pixel_accuracy": 0.7559}
    door_metrics = {
        "calibrated_f1": 0.6667,
        "mean_best_iou": 0.7182,
        "calibrated_score_threshold": 0.50,
    }
    segmentation_checkpoint = segmentation_dir / "best_model.pt"
    door_checkpoint = door_dir / "best_model.pt"
    _write_checkpoint(
        segmentation_checkpoint,
        model_name="BakeSmartLRASPP",
        manifest_sha="segmentation-split",
        metrics=segmentation_metrics,
        config={"validation_canvas_size": 640},
    )
    _write_checkpoint(
        door_checkpoint,
        model_name="BakeSmartDoorDetectorV6",
        manifest_sha="door-split",
        metrics=door_metrics,
    )
    _write_report(
        segmentation_dir / "validation_report.json",
        model_name="BakeSmartLRASPP",
        checkpoint=segmentation_checkpoint,
        manifest_sha="segmentation-split",
        metrics=segmentation_metrics,
    )
    _write_report(
        door_dir / "validation_report.json",
        model_name="BakeSmartDoorDetectorV6",
        checkpoint=door_checkpoint,
        manifest_sha="door-split",
        metrics=door_metrics,
        positives=2,
    )

    manifest = finalize(
        segmentation_dir=segmentation_dir,
        door_dir=door_dir,
        output_dir=output_dir,
    )

    assert manifest["status"] == "validation_only_unconfirmed_runtime"
    assert manifest["production_ready"] is False
    assert manifest["locked_test_used"] is False
    assert manifest["manual_classes"] == ["outlet"]
    assert manifest["runtime_policy"]["segmentation_inference"] == "single_pass"
    assert manifest["runtime_policy"]["segmentation_canvas_size"] == 320
    compact = torch.load(
        output_dir / "segmentation_model.pt", map_location="cpu", weights_only=False
    )
    assert "model_state_dict" in compact
    assert "optimizer_state_dict" not in compact


def test_finalize_rejects_weak_door_checkpoint(tmp_path):
    segmentation_dir = tmp_path / "segmentation"
    door_dir = tmp_path / "door"
    output_dir = tmp_path / "bundle"
    segmentation_metrics = {"mean_iou": 0.3987, "pixel_accuracy": 0.7559}
    door_metrics = {
        "calibrated_f1": 0.0,
        "mean_best_iou": 0.0,
        "calibrated_score_threshold": 0.50,
    }
    segmentation_checkpoint = segmentation_dir / "best_model.pt"
    door_checkpoint = door_dir / "best_model.pt"
    _write_checkpoint(
        segmentation_checkpoint,
        model_name="BakeSmartLRASPP",
        manifest_sha="segmentation-split",
        metrics=segmentation_metrics,
    )
    _write_checkpoint(
        door_checkpoint,
        model_name="BakeSmartDoorDetectorV6",
        manifest_sha="door-split",
        metrics=door_metrics,
    )
    _write_report(
        segmentation_dir / "validation_report.json",
        model_name="BakeSmartLRASPP",
        checkpoint=segmentation_checkpoint,
        manifest_sha="segmentation-split",
        metrics=segmentation_metrics,
    )
    _write_report(
        door_dir / "validation_report.json",
        model_name="BakeSmartDoorDetectorV6",
        checkpoint=door_checkpoint,
        manifest_sha="door-split",
        metrics=door_metrics,
        positives=2,
    )

    try:
        finalize(
            segmentation_dir=segmentation_dir,
            door_dir=door_dir,
            output_dir=output_dir,
        )
    except ValueError as exc:
        assert "below the validation-only runtime guard" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("weak Door checkpoint was accepted")
