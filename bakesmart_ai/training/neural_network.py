"""A small multi-task neural network implemented directly with NumPy.

No pretrained weights, hosted model, external inference API, or machine-learning
framework is used. Forward propagation, backpropagation, Adam, checkpointing,
and inference are implemented in this module.
"""

from __future__ import annotations

import io
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from training.model_data import ModelSplit


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / np.sum(exponentials, axis=1, keepdims=True)


def _is_weight_parameter(name: str) -> bool:
    """Return whether a parameter should receive L2 regularization."""

    return name.startswith("shared_w_") or name.endswith("_w")


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 20260818
    hidden_sizes: tuple[int, ...] = (64, 32)
    learning_rate: float = 0.003
    batch_size: int = 64
    max_epochs: int = 300
    patience: int = 35
    minimum_improvement: float = 1e-5
    l2_strength: float = 1e-4
    gradient_clip_norm: float = 5.0


@dataclass
class TrainingResult:
    history: list[dict[str, float | int]] = field(default_factory=list)
    best_epoch: int = 0
    stopped_epoch: int = 0
    best_validation_loss: float = math.inf


class MultiTaskMLP:
    """Shared hidden layers with one softmax head per recommendation target."""

    def __init__(
        self,
        input_size: int,
        hidden_sizes: tuple[int, ...],
        output_sizes: dict[str, int],
        seed: int,
    ) -> None:
        if input_size <= 0 or not hidden_sizes or any(size <= 0 for size in hidden_sizes):
            raise ValueError("model layer sizes must be positive")
        if not output_sizes or any(size < 2 for size in output_sizes.values()):
            raise ValueError("each output head must contain at least two classes")
        self.input_size = input_size
        self.hidden_sizes = tuple(hidden_sizes)
        self.output_sizes = dict(output_sizes)
        self.head_names = tuple(output_sizes)
        self.seed = seed
        self.parameters: dict[str, np.ndarray] = {}
        self._initialize_parameters()

    @property
    def parameter_count(self) -> int:
        return sum(parameter.size for parameter in self.parameters.values())

    def _initialize_parameters(self) -> None:
        rng = np.random.default_rng(self.seed)
        previous_size = self.input_size
        for index, size in enumerate(self.hidden_sizes):
            self.parameters[f"shared_w_{index}"] = rng.normal(
                0.0,
                math.sqrt(2.0 / previous_size),
                size=(previous_size, size),
            )
            self.parameters[f"shared_b_{index}"] = np.zeros(size, dtype=np.float64)
            previous_size = size
        for head_name, output_size in self.output_sizes.items():
            scale = math.sqrt(2.0 / (previous_size + output_size))
            self.parameters[f"head_{head_name}_w"] = rng.normal(
                0.0, scale, size=(previous_size, output_size)
            )
            self.parameters[f"head_{head_name}_b"] = np.zeros(
                output_size, dtype=np.float64
            )

    def forward(
        self, features: np.ndarray
    ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
        activation = features
        hidden_activations = [features]
        pre_activations: list[np.ndarray] = []
        for index in range(len(self.hidden_sizes)):
            pre_activation = (
                activation @ self.parameters[f"shared_w_{index}"]
                + self.parameters[f"shared_b_{index}"]
            )
            activation = np.maximum(pre_activation, 0.0)
            pre_activations.append(pre_activation)
            hidden_activations.append(activation)
        logits = {
            head_name: (
                activation @ self.parameters[f"head_{head_name}_w"]
                + self.parameters[f"head_{head_name}_b"]
            )
            for head_name in self.head_names
        }
        return logits, {
            "hidden_activations": hidden_activations,
            "pre_activations": pre_activations,
        }

    def predict_proba(self, features: np.ndarray) -> dict[str, np.ndarray]:
        logits, _ = self.forward(features)
        return {head: _softmax(values) for head, values in logits.items()}

    def predict(self, features: np.ndarray) -> dict[str, np.ndarray]:
        return {
            head: np.argmax(probabilities, axis=1)
            for head, probabilities in self.predict_proba(features).items()
        }

    def loss(
        self,
        features: np.ndarray,
        targets: dict[str, np.ndarray],
        l2_strength: float = 0.0,
    ) -> float:
        probabilities = self.predict_proba(features)
        row_indexes = np.arange(features.shape[0])
        losses = []
        for head_name in self.head_names:
            selected = probabilities[head_name][row_indexes, targets[head_name]]
            losses.append(float(-np.mean(np.log(np.clip(selected, 1e-12, 1.0)))))
        l2_penalty = 0.5 * l2_strength * sum(
            float(np.sum(parameter * parameter))
            for name, parameter in self.parameters.items()
            if _is_weight_parameter(name)
        )
        return float(np.mean(losses) + l2_penalty)

    def loss_and_gradients(
        self,
        features: np.ndarray,
        targets: dict[str, np.ndarray],
        l2_strength: float,
    ) -> tuple[float, dict[str, np.ndarray]]:
        logits, cache = self.forward(features)
        probabilities = {head: _softmax(values) for head, values in logits.items()}
        gradients: dict[str, np.ndarray] = {}
        row_indexes = np.arange(features.shape[0])
        head_count = len(self.head_names)
        head_losses: list[float] = []
        final_activation = cache["hidden_activations"][-1]
        shared_gradient = np.zeros_like(final_activation)

        for head_name in self.head_names:
            selected = probabilities[head_name][row_indexes, targets[head_name]]
            head_losses.append(float(-np.mean(np.log(np.clip(selected, 1e-12, 1.0)))))
            logits_gradient = probabilities[head_name].copy()
            logits_gradient[row_indexes, targets[head_name]] -= 1.0
            logits_gradient /= features.shape[0] * head_count
            weight_name = f"head_{head_name}_w"
            bias_name = f"head_{head_name}_b"
            gradients[weight_name] = (
                final_activation.T @ logits_gradient
                + l2_strength * self.parameters[weight_name]
            )
            gradients[bias_name] = np.sum(logits_gradient, axis=0)
            shared_gradient += logits_gradient @ self.parameters[weight_name].T

        hidden_activations = cache["hidden_activations"]
        pre_activations = cache["pre_activations"]
        for index in reversed(range(len(self.hidden_sizes))):
            pre_activation_gradient = shared_gradient * (pre_activations[index] > 0)
            weight_name = f"shared_w_{index}"
            bias_name = f"shared_b_{index}"
            gradients[weight_name] = (
                hidden_activations[index].T @ pre_activation_gradient
                + l2_strength * self.parameters[weight_name]
            )
            gradients[bias_name] = np.sum(pre_activation_gradient, axis=0)
            shared_gradient = pre_activation_gradient @ self.parameters[weight_name].T

        l2_penalty = 0.5 * l2_strength * sum(
            float(np.sum(parameter * parameter))
            for name, parameter in self.parameters.items()
            if _is_weight_parameter(name)
        )
        return float(np.mean(head_losses) + l2_penalty), gradients

    def state_dict(self) -> dict[str, np.ndarray]:
        return {name: value.copy() for name, value in self.parameters.items()}

    def load_state_dict(self, state: dict[str, np.ndarray]) -> None:
        if set(state) != set(self.parameters):
            raise ValueError("checkpoint parameter names do not match model architecture")
        for name, value in state.items():
            if value.shape != self.parameters[name].shape:
                raise ValueError(f"checkpoint shape mismatch for {name}")
            self.parameters[name] = np.asarray(value, dtype=np.float64).copy()

    def save(self, path: Path) -> None:
        """Write deterministic, pickle-free NPZ weights."""

        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(
            path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name, value in sorted(self.parameters.items()):
                buffer = io.BytesIO()
                np.save(buffer, value.astype(np.float64), allow_pickle=False)
                info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, buffer.getvalue(), compresslevel=9)

    @classmethod
    def load(
        cls,
        path: Path,
        input_size: int,
        hidden_sizes: tuple[int, ...],
        output_sizes: dict[str, int],
        seed: int,
    ) -> "MultiTaskMLP":
        model = cls(input_size, hidden_sizes, output_sizes, seed)
        with np.load(path, allow_pickle=False) as archive:
            state = {name: archive[name] for name in archive.files}
        model.load_state_dict(state)
        return model


class Adam:
    def __init__(
        self,
        parameters: dict[str, np.ndarray],
        learning_rate: float,
        beta_one: float = 0.9,
        beta_two: float = 0.999,
        epsilon: float = 1e-8,
    ) -> None:
        self.parameters = parameters
        self.learning_rate = learning_rate
        self.beta_one = beta_one
        self.beta_two = beta_two
        self.epsilon = epsilon
        self.step_count = 0
        self.first_moment = {name: np.zeros_like(value) for name, value in parameters.items()}
        self.second_moment = {name: np.zeros_like(value) for name, value in parameters.items()}

    def step(self, gradients: dict[str, np.ndarray], clip_norm: float) -> None:
        total_norm = math.sqrt(
            sum(float(np.sum(gradient * gradient)) for gradient in gradients.values())
        )
        scale = min(1.0, clip_norm / (total_norm + 1e-12))
        self.step_count += 1
        for name, parameter in self.parameters.items():
            gradient = gradients[name] * scale
            self.first_moment[name] = (
                self.beta_one * self.first_moment[name]
                + (1 - self.beta_one) * gradient
            )
            self.second_moment[name] = (
                self.beta_two * self.second_moment[name]
                + (1 - self.beta_two) * gradient * gradient
            )
            first_unbiased = self.first_moment[name] / (
                1 - self.beta_one**self.step_count
            )
            second_unbiased = self.second_moment[name] / (
                1 - self.beta_two**self.step_count
            )
            parameter -= self.learning_rate * first_unbiased / (
                np.sqrt(second_unbiased) + self.epsilon
            )


def _split_summary(
    model: MultiTaskMLP,
    split: ModelSplit,
    l2_strength: float,
) -> tuple[float, dict[str, float], float]:
    loss = model.loss(split.features, split.targets, l2_strength)
    predictions = model.predict(split.features)
    accuracies = {
        head: float(np.mean(predictions[head] == split.targets[head]))
        for head in model.head_names
    }
    return loss, accuracies, float(np.mean(list(accuracies.values())))


def train_multitask_model(
    model: MultiTaskMLP,
    train_split: ModelSplit,
    validation_split: ModelSplit,
    config: TrainConfig,
) -> TrainingResult:
    if train_split.name != "train" or validation_split.name != "validation":
        raise ValueError("model selection requires train and validation splits only")
    if set(train_split.scenario_ids) & set(validation_split.scenario_ids):
        raise ValueError("train and validation scenario IDs overlap")

    optimizer = Adam(model.parameters, learning_rate=config.learning_rate)
    rng = np.random.default_rng(config.seed + 1)
    best_state = model.state_dict()
    result = TrainingResult()
    epochs_without_improvement = 0

    for epoch in range(1, config.max_epochs + 1):
        indexes = rng.permutation(train_split.row_count)
        for start in range(0, train_split.row_count, config.batch_size):
            batch_indexes = indexes[start : start + config.batch_size]
            batch_targets = {
                head: values[batch_indexes]
                for head, values in train_split.targets.items()
            }
            _, gradients = model.loss_and_gradients(
                train_split.features[batch_indexes],
                batch_targets,
                config.l2_strength,
            )
            optimizer.step(gradients, config.gradient_clip_norm)

        train_loss, train_accuracy, train_mean = _split_summary(
            model, train_split, config.l2_strength
        )
        validation_loss, validation_accuracy, validation_mean = _split_summary(
            model, validation_split, config.l2_strength
        )
        history_row: dict[str, float | int] = {
            "epoch": epoch,
            "train_loss": train_loss,
            "validation_loss": validation_loss,
            "train_mean_accuracy": train_mean,
            "validation_mean_accuracy": validation_mean,
        }
        for head in model.head_names:
            history_row[f"train_accuracy__{head}"] = train_accuracy[head]
            history_row[f"validation_accuracy__{head}"] = validation_accuracy[head]
        result.history.append(history_row)

        if validation_loss < result.best_validation_loss - config.minimum_improvement:
            result.best_validation_loss = validation_loss
            result.best_epoch = epoch
            best_state = model.state_dict()
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        result.stopped_epoch = epoch
        if epochs_without_improvement >= config.patience:
            break

    model.load_state_dict(best_state)
    return result
