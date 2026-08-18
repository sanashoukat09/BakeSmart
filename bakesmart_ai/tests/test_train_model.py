from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from training import train_model as train_model_module
from training.model_data import load_model_split
from training.model_runtime import BootstrapModelRuntime
from training.neural_network import TrainConfig
from training.train_model import train_bootstrap_model


def test_training_requires_explicit_synthetic_acknowledgement(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit"):
        train_bootstrap_model(
            allow_synthetic_bootstrap=False,
            model_dir=tmp_path / "model",
            config=TrainConfig(max_epochs=1, patience=1),
        )


def test_short_training_run_writes_auditable_artifacts(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"

    result = train_bootstrap_model(
        allow_synthetic_bootstrap=True,
        evaluate_locked_test=True,
        model_dir=model_dir,
        config=TrainConfig(
            seed=17,
            hidden_sizes=(12, 8),
            max_epochs=2,
            patience=2,
            batch_size=128,
        ),
    )

    assert (model_dir / "model_weights.npz").is_file()
    assert (model_dir / "training_history.csv").is_file()
    assert (model_dir / "model_metadata.json").is_file()
    assert (model_dir / "evaluation_report.json").is_file()
    metadata = json.loads((model_dir / "model_metadata.json").read_text(encoding="utf-8"))
    assert metadata["initialization"]["pretrained_weights_used"] is False
    assert metadata["external_ai_api_used"] is False
    assert metadata["training"]["test_loaded_after_model_selection"] is True
    assert metadata["downstream_scene_contract"]["combined_3d_scene_required"] is True
    assert result["evaluation"]["test"]["records"] == 360

    runtime = BootstrapModelRuntime.load(model_dir)
    validation = load_model_split("validation")
    prediction = runtime.predict(validation.features[:1])[0]
    assert set(prediction) == {"theme", "cake", "decor", "layout"}
    assert all(0 <= value["confidence"] <= 1 for value in prediction.values())


def test_validation_only_training_does_not_open_locked_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded_splits: list[str] = []
    original_loader = train_model_module.load_model_split

    def tracked_loader(split: str, *args: object, **kwargs: object):
        loaded_splits.append(split)
        if split == "test":
            raise AssertionError("locked test must not be opened")
        return original_loader(split, *args, **kwargs)

    monkeypatch.setattr(train_model_module, "load_model_split", tracked_loader)
    result = train_bootstrap_model(
        allow_synthetic_bootstrap=True,
        evaluate_locked_test=False,
        model_dir=tmp_path / "validation-only-model",
        config=TrainConfig(
            seed=19,
            hidden_sizes=(8,),
            max_epochs=1,
            patience=1,
            batch_size=256,
        ),
    )

    assert loaded_splits == ["train", "validation"]
    assert result["evaluation"]["test"] is None


def test_runtime_rejects_nonfinite_features() -> None:
    runtime = BootstrapModelRuntime.load()
    features = np.zeros((1, len(runtime.feature_columns)))
    features[0, 0] = np.nan

    with pytest.raises(ValueError, match="finite"):
        runtime.predict(features)
