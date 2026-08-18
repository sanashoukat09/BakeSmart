from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from training.model_data import ModelSplit, load_model_split, load_preprocessing_metadata
from training.neural_network import (
    MultiTaskMLP,
    TrainConfig,
    train_multitask_model,
)
from training.prepare_dataset import DEFAULT_OUTPUT_DIR


def _small_model(seed: int = 7) -> MultiTaskMLP:
    return MultiTaskMLP(
        input_size=3,
        hidden_sizes=(4,),
        output_sizes={"head_one": 2, "head_two": 3},
        seed=seed,
    )


def test_forward_probabilities_are_valid() -> None:
    model = _small_model()
    features = np.asarray([[1.0, -1.0, 0.5], [0.2, 0.4, -0.8]])

    probabilities = model.predict_proba(features)

    assert set(probabilities) == {"head_one", "head_two"}
    for values in probabilities.values():
        assert np.all(values >= 0)
        assert np.allclose(values.sum(axis=1), 1.0)


def test_backpropagation_matches_finite_difference() -> None:
    model = _small_model()
    features = np.asarray(
        [
            [0.4, -0.2, 0.7],
            [1.1, 0.3, -0.5],
            [-0.6, 0.8, 0.2],
            [0.5, 0.9, -1.0],
        ]
    )
    targets = {
        "head_one": np.asarray([0, 1, 0, 1]),
        "head_two": np.asarray([2, 1, 0, 2]),
    }
    _, gradients = model.loss_and_gradients(features, targets, l2_strength=0.01)
    epsilon = 1e-6

    for parameter_name, index in (
        ("shared_w_0", (1, 2)),
        ("shared_b_0", (3,)),
        ("head_head_one_w", (2, 1)),
        ("head_head_two_b", (2,)),
    ):
        parameter = model.parameters[parameter_name]
        original = float(parameter[index])
        parameter[index] = original + epsilon
        plus = model.loss(features, targets, l2_strength=0.01)
        parameter[index] = original - epsilon
        minus = model.loss(features, targets, l2_strength=0.01)
        parameter[index] = original
        numerical = (plus - minus) / (2 * epsilon)
        assert gradients[parameter_name][index] == pytest.approx(
            numerical, rel=2e-5, abs=2e-6
        )


def test_checkpoint_is_deterministic_and_pickle_free(tmp_path: Path) -> None:
    model = _small_model()
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"

    model.save(first)
    model.save(second)
    loaded = MultiTaskMLP.load(
        first,
        input_size=3,
        hidden_sizes=(4,),
        output_sizes={"head_one": 2, "head_two": 3},
        seed=999,
    )

    assert first.read_bytes() == second.read_bytes()
    assert hashlib.sha256(first.read_bytes()).hexdigest() == hashlib.sha256(
        second.read_bytes()
    ).hexdigest()
    features = np.asarray([[0.1, 0.2, 0.3]])
    for head in model.head_names:
        assert np.allclose(
            model.predict_proba(features)[head], loaded.predict_proba(features)[head]
        )


def test_phase4_model_matrices_are_disjoint_and_numeric() -> None:
    metadata = load_preprocessing_metadata(DEFAULT_OUTPUT_DIR)
    train = load_model_split("train", DEFAULT_OUTPUT_DIR, metadata)
    validation = load_model_split("validation", DEFAULT_OUTPUT_DIR, metadata)
    test = load_model_split("test", DEFAULT_OUTPUT_DIR, metadata)

    assert train.features.shape == (1680, 42)
    assert validation.features.shape == (360, 42)
    assert test.features.shape == (360, 42)
    assert not set(train.scenario_ids) & set(validation.scenario_ids)
    assert not set(train.scenario_ids) & set(test.scenario_ids)
    assert np.isfinite(train.features).all()


def test_training_is_reproducible_for_same_seed() -> None:
    metadata = load_preprocessing_metadata(DEFAULT_OUTPUT_DIR)
    train_source = load_model_split("train", DEFAULT_OUTPUT_DIR, metadata)
    validation_source = load_model_split("validation", DEFAULT_OUTPUT_DIR, metadata)
    train = ModelSplit(
        "train",
        train_source.scenario_ids[:128],
        train_source.features[:128],
        {head: values[:128] for head, values in train_source.targets.items()},
    )
    validation = ModelSplit(
        "validation",
        validation_source.scenario_ids[:64],
        validation_source.features[:64],
        {head: values[:64] for head, values in validation_source.targets.items()},
    )
    output_sizes = {
        head: len(set(train_source.targets[head])) for head in train_source.targets
    }
    config = TrainConfig(
        seed=11,
        hidden_sizes=(12, 8),
        max_epochs=4,
        patience=4,
        batch_size=32,
    )
    first = MultiTaskMLP(42, config.hidden_sizes, output_sizes, config.seed)
    second = MultiTaskMLP(42, config.hidden_sizes, output_sizes, config.seed)

    first_result = train_multitask_model(first, train, validation, config)
    second_result = train_multitask_model(second, train, validation, config)

    assert first_result.history == second_result.history
    for name in first.parameters:
        assert np.array_equal(first.parameters[name], second.parameters[name])
