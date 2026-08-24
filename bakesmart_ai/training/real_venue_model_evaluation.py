"""Shared, leakage-safe evaluation helpers for the real venue model.

Validation and final locked-test evaluation use the same 512-pixel letterbox
and overlapping-tile inference path. Training code may never call
``locked_test_samples``; that loader exists only for the explicit Step-5
evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyTorch is required for real venue evaluation. Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR, UNLABELLED_ID
from training.real_venue_segmentation import (
    BakeSmartVenueUNet,
    CLASS_NAMES,
    SegmentationConfusion,
    SplitSample,
    _safe_project_path,
    _validate_mask_values,
    sha256_file,
)
from training.real_venue_segmentation_v2 import tiled_logits


@dataclass(frozen=True)
class LetterboxTransform:
    canvas_size: int
    left: int
    top: int
    resized_width: int
    resized_height: int


def load_checkpoint_model(
    checkpoint_path: Path,
    *,
    device: torch.device,
    expected_manifest_sha256: str,
) -> tuple[BakeSmartVenueUNet, dict[str, object]]:
    checkpoint_path = Path(checkpoint_path).resolve()
    if not checkpoint_path.is_file():
        raise ValueError(f"model checkpoint is missing: {checkpoint_path}")
    payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if not isinstance(payload, dict):
        raise ValueError("model checkpoint must contain a metadata dictionary")
    if payload.get("model_name") != "BakeSmartVenueUNet":
        raise ValueError("checkpoint model name is not BakeSmartVenueUNet")
    if payload.get("class_names") != list(CLASS_NAMES):
        raise ValueError("checkpoint does not use the six-class BakeSmart schema")
    if payload.get("pretrained") is not False:
        raise ValueError("selected checkpoint must not use pretrained weights")
    if payload.get("random_initialization") is not True:
        raise ValueError("selected checkpoint must record random initialization")
    if payload.get("test_data_used") is not False:
        raise ValueError("candidate checkpoint was exposed to locked-test data")
    if str(payload.get("manifest_sha256") or "") != expected_manifest_sha256:
        raise ValueError("checkpoint was trained against a different locked split")
    config = payload.get("config")
    if not isinstance(config, dict):
        raise ValueError("checkpoint has no configuration metadata")
    base_channels = int(config.get("base_channels", 0))
    model = BakeSmartVenueUNet(base_channels=base_channels).to(device)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    model.eval()
    return model, payload


def letterbox_image(
    image: Image.Image,
    *,
    canvas_size: int = 512,
) -> tuple[torch.Tensor, LetterboxTransform]:
    if canvas_size < 64 or canvas_size % 16 != 0:
        raise ValueError("canvas size must be at least 64 and divisible by 16")
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    scale = min(canvas_size / width, canvas_size / height)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized = image.resize(
        (resized_width, resized_height), Image.Resampling.BILINEAR
    )
    canvas = Image.new("RGB", (canvas_size, canvas_size), (127, 127, 127))
    left = (canvas_size - resized_width) // 2
    top = (canvas_size - resized_height) // 2
    canvas.paste(resized, (left, top))
    pixels = np.asarray(canvas, dtype=np.float32) / 255.0
    pixels = (pixels - 0.5) / 0.5
    tensor = torch.from_numpy(pixels.transpose(2, 0, 1)).float().unsqueeze(0)
    return tensor, LetterboxTransform(
        canvas_size=canvas_size,
        left=left,
        top=top,
        resized_width=resized_width,
        resized_height=resized_height,
    )


def letterbox_mask(
    mask: Image.Image,
    transform: LetterboxTransform,
    *,
    scene_id: str,
) -> torch.Tensor:
    mask = mask.convert("L")
    resized = mask.resize(
        (transform.resized_width, transform.resized_height),
        Image.Resampling.NEAREST,
    )
    canvas = Image.new(
        "L",
        (transform.canvas_size, transform.canvas_size),
        UNLABELLED_ID,
    )
    canvas.paste(resized, (transform.left, transform.top))
    values = np.asarray(canvas, dtype=np.uint8).copy()
    _validate_mask_values(values, scene_id)
    return torch.from_numpy(values.astype(np.int64)).unsqueeze(0)


@torch.no_grad()
def predict_logits(
    model: torch.nn.Module,
    image: torch.Tensor,
    *,
    device: torch.device,
    tile_size: int = 256,
    tile_stride: int = 192,
) -> torch.Tensor:
    model.eval()
    image = image.to(device)
    return tiled_logits(
        model,
        image,
        tile_size=tile_size,
        stride=tile_stride,
    )


def evaluate_samples(
    model: torch.nn.Module,
    samples: list[SplitSample],
    *,
    device: torch.device,
    canvas_size: int = 512,
    tile_size: int = 256,
    tile_stride: int = 192,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if not samples:
        raise ValueError("evaluation sample list is empty")
    combined = SegmentationConfusion()
    per_scene: list[dict[str, object]] = []
    for sample in samples:
        with Image.open(sample.image_path) as image_source:
            image_tensor, transform = letterbox_image(
                image_source, canvas_size=canvas_size
            )
        with Image.open(sample.mask_path) as mask_source:
            mask_tensor = letterbox_mask(
                mask_source,
                transform,
                scene_id=sample.scene_id,
            )
        logits = predict_logits(
            model,
            image_tensor,
            device=device,
            tile_size=tile_size,
            tile_stride=tile_stride,
        )
        predictions = torch.argmax(logits, dim=1).cpu()
        combined.update(mask_tensor, predictions)
        scene_confusion = SegmentationConfusion()
        scene_confusion.update(mask_tensor, predictions)
        per_scene.append(
            {"scene_id": sample.scene_id, "metrics": scene_confusion.metrics()}
        )
    return combined.metrics(), per_scene


def locked_test_samples(
    manifest: dict[str, object],
    *,
    project_dir: Path = PROJECT_DIR,
    verify_hashes: bool = True,
) -> list[SplitSample]:
    """Load the test split only for the explicit final evaluator."""
    root = Path(project_dir).resolve()
    samples: list[SplitSample] = []
    for row in manifest["scenes"]:
        if row.get("split") != "test":
            continue
        scene_id = str(row["scene_id"])
        image_path = _safe_project_path(root, str(row["image_path"]))
        mask_path = _safe_project_path(root, str(row["mask_path"]))
        if not image_path.is_file() or not mask_path.is_file():
            raise ValueError(f"locked-test files are missing: {scene_id}")
        image_sha = str(row.get("image_sha256") or "")
        mask_sha = str(row.get("mask_sha256") or "")
        if verify_hashes and (
            sha256_file(image_path) != image_sha
            or sha256_file(mask_path) != mask_sha
        ):
            raise ValueError(f"locked-test checksum changed: {scene_id}")
        samples.append(
            SplitSample(
                scene_id=scene_id,
                split="test",
                image_path=image_path,
                mask_path=mask_path,
                image_sha256=image_sha,
                mask_sha256=mask_sha,
            )
        )
    expected = int(manifest["counts"]["test"])
    if len(samples) != expected or expected <= 0:
        raise ValueError("locked-test sample count does not match the manifest")
    return samples
