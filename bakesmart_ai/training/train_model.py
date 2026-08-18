"""Train BakeSmart's synthetic bootstrap recommendation model from scratch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping

from training.metrics import evaluate_multitask_model
from training.model_data import load_model_split, load_preprocessing_metadata
from training.neural_network import (
    MultiTaskMLP,
    TrainConfig,
    TrainingResult,
    train_multitask_model,
)
from training.prepare_dataset import DEFAULT_OUTPUT_DIR
from training.preprocessing import TARGET_FIELDS
from training.validate_datasets import DEFAULT_DATA_DIR, validate_data_directory


DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "bootstrap_v1"
HISTORY_COLUMNS = [
    "epoch",
    "train_loss",
    "validation_loss",
    "train_mean_accuracy",
    "validation_mean_accuracy",
    "train_accuracy__target__theme",
    "validation_accuracy__target__theme",
    "train_accuracy__target__cake",
    "validation_accuracy__target__cake",
    "train_accuracy__target__decor",
    "validation_accuracy__target__decor",
    "train_accuracy__target__layout",
    "validation_accuracy__target__layout",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(value, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _write_history(path: Path, result: TrainingResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in result.history:
            writer.writerow(
                {
                    column: row[column]
                    if column == "epoch"
                    else format(float(row[column]), ".12g")
                    for column in HISTORY_COLUMNS
                }
            )


def _labels_by_head(metadata: dict[str, object]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    mappings = metadata["target_label_to_id"]
    for source_field, head_name in TARGET_FIELDS.items():
        label_to_id = mappings[source_field]
        labels[head_name] = [
            label for label, _ in sorted(label_to_id.items(), key=lambda item: item[1])
        ]
    return labels


def _verify_phase4(
    data_dir: Path,
    processed_dir: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    source_validation = validate_data_directory(data_dir)
    if not source_validation.valid:
        raise ValueError(f"Phase 3 source validation failed: {source_validation.to_dict()}")
    preparation_report = json.loads(
        (processed_dir / "preparation_report.json").read_text(encoding="utf-8")
    )
    if not preparation_report["training_gate"]["synthetic_bootstrap_pipeline_ready"]:
        raise ValueError("Phase 4 did not approve the synthetic bootstrap pipeline")
    preprocessing = load_preprocessing_metadata(processed_dir)
    for split, expected_hash in preprocessing["processed_split_sha256"].items():
        actual_hash = _sha256(processed_dir / f"{split}.csv")
        if actual_hash != expected_hash:
            raise ValueError(f"processed {split} checksum does not match Phase 4 metadata")
    return preparation_report, preprocessing


def train_bootstrap_model(
    *,
    allow_synthetic_bootstrap: bool,
    evaluate_locked_test: bool = False,
    data_dir: Path = DEFAULT_DATA_DIR,
    processed_dir: Path = DEFAULT_OUTPUT_DIR,
    model_dir: Path = DEFAULT_MODEL_DIR,
    config: TrainConfig | None = None,
) -> dict[str, object]:
    """Train locally; the test matrix is loaded only after model selection."""

    if not allow_synthetic_bootstrap:
        raise ValueError(
            "synthetic labels require explicit --allow-synthetic-bootstrap acknowledgement"
        )
    config = config or TrainConfig()
    data_dir = data_dir.resolve()
    processed_dir = processed_dir.resolve()
    model_dir = model_dir.resolve()
    preparation_report, preprocessing = _verify_phase4(data_dir, processed_dir)

    labels_by_head = _labels_by_head(preprocessing)
    output_sizes = {head: len(labels) for head, labels in labels_by_head.items()}

    # Deliberately load only train and validation before model selection.
    train_split = load_model_split("train", processed_dir, preprocessing)
    validation_split = load_model_split("validation", processed_dir, preprocessing)
    model = MultiTaskMLP(
        input_size=train_split.features.shape[1],
        hidden_sizes=config.hidden_sizes,
        output_sizes=output_sizes,
        seed=config.seed,
    )
    initial_state_hash = hashlib.sha256(
        b"".join(
            value.tobytes() for _, value in sorted(model.state_dict().items())
        )
    ).hexdigest()
    training_result = train_multitask_model(
        model,
        train_split,
        validation_split,
        config,
    )

    model_dir.mkdir(parents=True, exist_ok=True)
    weights_path = model_dir / "model_weights.npz"
    history_path = model_dir / "training_history.csv"
    model.save(weights_path)
    _write_history(history_path, training_result)

    validation_metrics = evaluate_multitask_model(model, validation_split, labels_by_head)
    test_metrics: dict[str, object] | None = None
    if evaluate_locked_test:
        # The locked test split is first opened here, after early stopping and restore.
        test_split = load_model_split("test", processed_dir, preprocessing)
        test_metrics = evaluate_multitask_model(model, test_split, labels_by_head)

    weights_hash = _sha256(weights_path)
    history_hash = _sha256(history_path)
    metadata: dict[str, object] = {
        "model_name": "BakeSmartMultiTaskMLP",
        "model_version": "bootstrap-v1",
        "artifact_status": "synthetic_bootstrap_only",
        "production_approved": False,
        "implementation": "NumPy forward/backpropagation and Adam implemented locally",
        "initialization": {
            "type": "random_he_and_xavier",
            "seed": config.seed,
            "initial_state_sha256": initial_state_hash,
            "pretrained_weights_used": False,
        },
        "external_ai_api_used": False,
        "architecture": {
            "input_size": model.input_size,
            "hidden_sizes": list(model.hidden_sizes),
            "output_sizes": model.output_sizes,
            "parameter_count": model.parameter_count,
            "activation": "relu",
            "output_activation": "softmax_per_head",
        },
        "training": {
            "config": asdict(config),
            "selection_split": "validation",
            "test_loaded_after_model_selection": evaluate_locked_test,
            "best_epoch": training_result.best_epoch,
            "stopped_epoch": training_result.stopped_epoch,
            "best_validation_loss": training_result.best_validation_loss,
        },
        "data": {
            "label_type": "synthetic_rule_based_silver",
            "training_rows": train_split.row_count,
            "validation_rows": validation_split.row_count,
            "test_rows": preprocessing["split_counts"]["test"],
            "feature_columns": preprocessing["feature_columns"],
            "target_columns": preprocessing["target_columns"],
            "target_label_to_id": preprocessing["target_label_to_id"],
            "processed_split_sha256": preprocessing["processed_split_sha256"],
            "production_accuracy_training_ready": preparation_report["training_gate"][
                "production_accuracy_training_ready"
            ],
        },
        "artifacts": {
            "weights_file": weights_path.name,
            "weights_sha256": weights_hash,
            "history_file": history_path.name,
            "history_sha256": history_hash,
        },
        "downstream_scene_contract": {
            "predictions": ["theme", "cake", "decor", "layout"],
            "combined_3d_scene_required": True,
            "scene_layers": [
                "cake_and_baked_items",
                "dessert_table",
                "decorations",
                "backdrop",
                "lighting",
            ],
            "note": (
                "Phase 6 maps predictions and budget rules to catalogue IDs; the 3D "
                "service must display selected baked items and decorations together."
            ),
        },
    }
    _write_json(model_dir / "model_metadata.json", metadata)

    evaluation_report: dict[str, object] = {
        "model_name": metadata["model_name"],
        "model_version": metadata["model_version"],
        "weights_sha256": weights_hash,
        "evaluation_order": [
            "validation",
            *(["locked_test_after_model_selection"] if evaluate_locked_test else []),
        ],
        "validation": validation_metrics,
        "test": test_metrics,
        "limitations": [
            "All current labels are synthetic rule-generated silver labels.",
            "Metrics measure recovery of bootstrap rules, not customer satisfaction.",
            "No real-world independently labelled test set is available yet.",
            "Cake serving, pricing, safety, and placement require professional review.",
        ],
    }
    _write_json(model_dir / "evaluation_report.json", evaluation_report)
    return {
        "metadata": metadata,
        "evaluation": evaluation_report,
        "model_dir": str(model_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-synthetic-bootstrap", action="store_true")
    parser.add_argument(
        "--evaluate-locked-test",
        action="store_true",
        help="Evaluate the locked test split once, after validation-based model selection",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--seed", type=int, default=TrainConfig.seed)
    parser.add_argument("--max-epochs", type=int, default=TrainConfig.max_epochs)
    parser.add_argument("--patience", type=int, default=TrainConfig.patience)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    config = TrainConfig(
        seed=args.seed,
        max_epochs=args.max_epochs,
        patience=args.patience,
    )
    try:
        result = train_bootstrap_model(
            allow_synthetic_bootstrap=args.allow_synthetic_bootstrap,
            evaluate_locked_test=args.evaluate_locked_test,
            data_dir=args.data_dir,
            processed_dir=args.processed_dir,
            model_dir=args.model_dir,
            config=config,
        )
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        metadata = result["metadata"]
        evaluation = result["evaluation"]
        print(
            "PASS: trained BakeSmartMultiTaskMLP from random weights; "
            f"best epoch {metadata['training']['best_epoch']}"
        )
        accuracy_message = (
            "Synthetic bootstrap mean accuracy: "
            f"validation={evaluation['validation']['mean_accuracy']:.4f}"
        )
        if evaluation["test"] is not None:
            accuracy_message += f", test={evaluation['test']['mean_accuracy']:.4f}"
        print(accuracy_message)
        print("WARNING: synthetic bootstrap metrics are not real-world accuracy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
