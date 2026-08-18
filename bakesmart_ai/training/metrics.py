"""Dependency-light classification metrics for BakeSmart model evaluation."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from training.model_data import ModelSplit
from training.neural_network import MultiTaskMLP


def classification_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    labels: Sequence[str],
) -> dict[str, object]:
    class_count = len(labels)
    confusion = np.zeros((class_count, class_count), dtype=np.int64)
    for actual_id, predicted_id in zip(actual, predicted, strict=True):
        confusion[int(actual_id), int(predicted_id)] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []
    for class_id, label in enumerate(labels):
        true_positive = int(confusion[class_id, class_id])
        false_positive = int(confusion[:, class_id].sum() - true_positive)
        false_negative = int(confusion[class_id, :].sum() - true_positive)
        support = int(confusion[class_id, :].sum())
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
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    return {
        "accuracy": float(np.mean(actual == predicted)),
        "macro_precision": float(np.mean(precisions)),
        "macro_recall": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1_scores)),
        "confusion_matrix": confusion.tolist(),
        "class_order": list(labels),
        "per_class": per_class,
    }


def evaluate_multitask_model(
    model: MultiTaskMLP,
    split: ModelSplit,
    labels_by_head: dict[str, list[str]],
) -> dict[str, object]:
    predictions = model.predict(split.features)
    targets: dict[str, object] = {}
    accuracies: list[float] = []
    for head_name in model.head_names:
        metrics = classification_metrics(
            split.targets[head_name],
            predictions[head_name],
            labels_by_head[head_name],
        )
        targets[head_name] = metrics
        accuracies.append(float(metrics["accuracy"]))
    return {
        "split": split.name,
        "records": split.row_count,
        "mean_accuracy": float(np.mean(accuracies)),
        "targets": targets,
    }
