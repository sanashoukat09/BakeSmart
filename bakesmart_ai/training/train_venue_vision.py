"""Train BakeSmart's synthetic venue segmenter from random NumPy weights."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from training.neural_network import (
    MultiTaskMLP,
    TrainConfig,
    TrainingResult,
    train_multitask_model,
)
from training.venue_vision_data import (
    DEFAULT_VENUE_DATA_DIR,
    LABEL_TO_ID,
    VENUE_LABELS,
    VenueSceneRecord,
    build_pixel_split,
    extract_pixel_features,
    load_index,
    render_synthetic_scene,
)


DEFAULT_VENUE_MODEL_DIR = (
    Path(__file__).resolve().parents[1] / "models" / "venue_vision_bootstrap_v1"
)
DEFAULT_VENUE_CONFIG = TrainConfig(
    seed=20260820,
    hidden_sizes=(48, 24),
    learning_rate=0.003,
    batch_size=1024,
    max_epochs=80,
    patience=10,
    minimum_improvement=1e-5,
    l2_strength=1e-4,
    gradient_clip_norm=5.0,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _write_history(path: Path, result: TrainingResult) -> None:
    columns = (
        "epoch",
        "train_loss",
        "validation_loss",
        "train_mean_accuracy",
        "validation_mean_accuracy",
        "train_accuracy__segmentation",
        "validation_accuracy__segmentation",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in result.history:
            writer.writerow(
                {
                    column: (
                        row[column]
                        if column == "epoch"
                        else format(float(row[column]), ".12g")
                    )
                    for column in columns
                }
            )


def segmentation_metrics(confusion: np.ndarray) -> dict[str, object]:
    per_class: dict[str, dict[str, float | int]] = {}
    iou_values: list[float] = []
    for class_id, label in enumerate(VENUE_LABELS):
        true_positive = int(confusion[class_id, class_id])
        false_positive = int(confusion[:, class_id].sum() - true_positive)
        false_negative = int(confusion[class_id, :].sum() - true_positive)
        support = int(confusion[class_id, :].sum())
        union = true_positive + false_positive + false_negative
        iou = true_positive / union if union else 0.0
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        iou_values.append(iou)
        per_class[label] = {
            "iou": iou,
            "precision": precision,
            "recall": recall,
            "support_pixels": support,
        }
    total = int(confusion.sum())
    return {
        "pixel_accuracy": float(np.trace(confusion) / total) if total else 0.0,
        "macro_iou": float(np.mean(iou_values)),
        "class_order": list(VENUE_LABELS),
        "confusion_matrix": confusion.tolist(),
        "per_class": per_class,
        "pixels": total,
    }


def evaluate_scene_split(
    model: MultiTaskMLP,
    records: list[VenueSceneRecord],
    split: str,
    *,
    image_size: int = 48,
) -> dict[str, object]:
    confusion = np.zeros((len(VENUE_LABELS), len(VENUE_LABELS)), dtype=np.int64)
    scene_count = 0
    for record in records:
        if record.split != split:
            continue
        image, mask = render_synthetic_scene(record.seed, size=image_size)
        prediction = model.predict(extract_pixel_features(image))["segmentation"]
        actual = mask.reshape(-1)
        np.add.at(confusion, (actual, prediction), 1)
        scene_count += 1
    if not scene_count:
        raise ValueError(f"venue evaluation split {split!r} is empty")
    metrics = segmentation_metrics(confusion)
    metrics["split"] = split
    metrics["scenes"] = scene_count
    return metrics


def train_venue_vision_model(
    *,
    allow_synthetic_bootstrap: bool,
    evaluate_locked_test: bool = False,
    data_dir: Path = DEFAULT_VENUE_DATA_DIR,
    model_dir: Path = DEFAULT_VENUE_MODEL_DIR,
    config: TrainConfig = DEFAULT_VENUE_CONFIG,
) -> dict[str, object]:
    if not allow_synthetic_bootstrap:
        raise ValueError(
            "synthetic venue labels require --allow-synthetic-bootstrap acknowledgement"
        )
    records = load_index(data_dir)
    dataset_report = json.loads(
        (data_dir / "dataset_report.json").read_text(encoding="utf-8")
    )
    if not dataset_report["training_gate"]["synthetic_bootstrap_ready"]:
        raise ValueError("venue dataset report did not approve synthetic bootstrap")
    train_scene_ids = {record.scene_id for record in records if record.split == "train"}
    validation_scene_ids = {
        record.scene_id for record in records if record.split == "validation"
    }
    test_scene_ids = {record.scene_id for record in records if record.split == "test"}
    if train_scene_ids & validation_scene_ids or train_scene_ids & test_scene_ids:
        raise ValueError("venue scene IDs overlap locked splits")
    if validation_scene_ids & test_scene_ids:
        raise ValueError("venue validation and test scene IDs overlap")

    train_split = build_pixel_split("train", records)
    validation_split = build_pixel_split("validation", records)
    model = MultiTaskMLP(
        input_size=train_split.features.shape[1],
        hidden_sizes=config.hidden_sizes,
        output_sizes={"segmentation": len(VENUE_LABELS)},
        seed=config.seed,
    )
    initial_state_hash = hashlib.sha256(
        b"".join(value.tobytes() for _, value in sorted(model.state_dict().items()))
    ).hexdigest()
    result = train_multitask_model(model, train_split, validation_split, config)

    model_dir.mkdir(parents=True, exist_ok=True)
    weights_path = model_dir / "model_weights.npz"
    history_path = model_dir / "training_history.csv"
    model.save(weights_path)
    _write_history(history_path, result)
    validation = evaluate_scene_split(model, records, "validation")
    test = (
        evaluate_scene_split(model, records, "test") if evaluate_locked_test else None
    )

    metadata: dict[str, object] = {
        "model_name": "BakeSmartVenuePixelMLP",
        "model_version": "venue-vision-bootstrap-v1",
        "artifact_status": "synthetic_bootstrap_only",
        "production_approved": False,
        "external_ai_api_used": False,
        "pretrained_weights_used": False,
        "implementation": "NumPy patch features, forward/backpropagation, and Adam implemented locally",
        "initialization": {
            "type": "random_he_and_xavier",
            "seed": config.seed,
            "initial_state_sha256": initial_state_hash,
        },
        "architecture": {
            "input_features": train_split.features.shape[1],
            "input_patch": "3x3 RGB plus normalized x/y coordinates",
            "hidden_sizes": list(config.hidden_sizes),
            "classes": list(VENUE_LABELS),
            "label_to_id": LABEL_TO_ID,
            "parameter_count": model.parameter_count,
            "activation": "relu",
            "output_activation": "softmax",
        },
        "training": {
            "config": asdict(config),
            "best_epoch": result.best_epoch,
            "stopped_epoch": result.stopped_epoch,
            "best_validation_loss": result.best_validation_loss,
            "selection_split": "validation",
            "test_pixels_rendered_after_model_selection": evaluate_locked_test,
        },
        "data": {
            "label_type": "deterministic_synthetic_pixel_masks",
            "scene_counts": {
                "train": len(train_scene_ids),
                "validation": len(validation_scene_ids),
                "test": len(test_scene_ids),
            },
            "balanced_training_pixels": train_split.row_count,
            "balanced_validation_pixels": validation_split.row_count,
            "image_size": 48,
            "real_annotation_rows": dataset_report["real_annotation_rows"],
            "approved_real_annotation_rows": dataset_report[
                "approved_real_annotation_rows"
            ],
        },
        "runtime_policy": {
            "detections_are_candidates_only": True,
            "maximum_reported_confidence": 0.49,
            "automatic_obstacle_confirmation": False,
            "automatic_scale_estimation": False,
        },
    }
    _write_json(model_dir / "model_metadata.json", metadata)
    evaluation: dict[str, object] = {
        "model_name": metadata["model_name"],
        "model_version": metadata["model_version"],
        "weights_sha256": _sha256(weights_path),
        "evaluation_order": [
            "validation",
            *(["locked_test_after_model_selection"] if test is not None else []),
        ],
        "validation": validation,
        "test": test,
        "limitations": [
            "All training masks are deterministic synthetic bootstrap labels.",
            "Metrics measure synthetic scene recovery, not accuracy on customer photos.",
            "No independently labelled real-photo test set exists yet.",
            "Runtime detections are unconfirmed candidates and never create obstacles automatically.",
        ],
    }
    _write_json(model_dir / "evaluation_report.json", evaluation)
    metadata["artifacts"] = {
        "weights_file": weights_path.name,
        "weights_sha256": _sha256(weights_path),
        "history_file": history_path.name,
        "history_sha256": _sha256(history_path),
    }
    _write_json(model_dir / "model_metadata.json", metadata)
    return {"metadata": metadata, "evaluation": evaluation}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-synthetic-bootstrap", action="store_true")
    parser.add_argument("--evaluate-locked-test", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_VENUE_DATA_DIR)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_VENUE_MODEL_DIR)
    parser.add_argument(
        "--max-epochs", type=int, default=DEFAULT_VENUE_CONFIG.max_epochs
    )
    parser.add_argument("--patience", type=int, default=DEFAULT_VENUE_CONFIG.patience)
    args = parser.parse_args()
    config = TrainConfig(
        **{
            **asdict(DEFAULT_VENUE_CONFIG),
            "max_epochs": args.max_epochs,
            "patience": args.patience,
        }
    )
    try:
        result = train_venue_vision_model(
            allow_synthetic_bootstrap=args.allow_synthetic_bootstrap,
            evaluate_locked_test=args.evaluate_locked_test,
            data_dir=args.data_dir,
            model_dir=args.model_dir,
            config=config,
        )
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1
    validation = result["evaluation"]["validation"]
    print(
        "PASS: trained BakeSmartVenuePixelMLP from random weights; "
        f"validation macro IoU={validation['macro_iou']:.4f}"
    )
    if result["evaluation"]["test"] is not None:
        print(
            "Locked synthetic test macro IoU: "
            f"{result['evaluation']['test']['macro_iou']:.4f}"
        )
    print("WARNING: synthetic segmentation metrics are not real-photo accuracy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
