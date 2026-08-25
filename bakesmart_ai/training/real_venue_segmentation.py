"""Real-photo six-class venue segmentation components for BakeSmart.

This module contains the Step-4 dataset loader, a compact U-Net initialized from
random weights, augmentation, class weighting, loss, and segmentation metrics.
It never downloads or loads pretrained weights.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import torch
    from torch import nn
    from torch.utils.data import Dataset
except ImportError as exc:  # pragma: no cover - gives a useful CLI error
    raise ImportError(
        "PyTorch is required for Step 4. Install project requirements with: "
        "pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR, UNLABELLED_ID
from training.semantic_annotation_workspace import (
    SEMANTIC_LABEL_CLASSES,
    SEMANTIC_LABEL_IDS,
)


NUM_CLASSES = len(SEMANTIC_LABEL_IDS)
CLASS_NAMES = tuple(label.key for label in SEMANTIC_LABEL_CLASSES)
TRAINABLE_SPLITS = {"train", "validation"}


@dataclass(frozen=True)
class SplitSample:
    scene_id: str
    split: str
    image_path: Path
    mask_path: Path
    image_sha256: str
    mask_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_locked_split_manifest(
    manifest_path: Path,
    *,
    project_dir: Path = PROJECT_DIR,
    expected_dataset: str = "real_v2",
) -> dict[str, object]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"split manifest is unreadable: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("split manifest must be a JSON object")
    if manifest.get("dataset") != expected_dataset:
        raise ValueError(
            f"Step 4 requires the locked {expected_dataset} split"
        )
    if manifest.get("test_set_locked") is not True:
        raise ValueError("Step 4 requires test_set_locked=true")
    if manifest.get("semantic_class_ids") != list(SEMANTIC_LABEL_IDS):
        raise ValueError("split manifest semantic classes do not match six-class Step 4")
    rows = manifest.get("scenes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("split manifest has no scene rows")

    seen: set[str] = set()
    split_counts = {"train": 0, "validation": 0, "test": 0}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("split manifest contains an invalid scene row")
        scene_id = str(row.get("scene_id") or "")
        split = str(row.get("split") or "")
        if not scene_id or scene_id in seen:
            raise ValueError(f"duplicate or empty scene ID in split manifest: {scene_id}")
        if split not in split_counts:
            raise ValueError(f"invalid split for {scene_id}: {split}")
        seen.add(scene_id)
        split_counts[split] += 1

    recorded_counts = manifest.get("counts")
    if not isinstance(recorded_counts, dict):
        raise ValueError("split manifest has no count summary")
    expected = {key: int(recorded_counts[key]) for key in split_counts}
    if split_counts != expected:
        raise ValueError(
            f"split manifest count mismatch: rows={split_counts}, summary={expected}"
        )
    if min(split_counts.values()) <= 0:
        raise ValueError("train, validation and test splits must all be non-empty")
    return manifest


def samples_for_split(
    manifest: dict[str, object],
    split: str,
    *,
    project_dir: Path = PROJECT_DIR,
    verify_hashes: bool = True,
) -> list[SplitSample]:
    """Return train or validation samples only. Test is deliberately forbidden."""
    if split not in TRAINABLE_SPLITS:
        raise ValueError(
            "Step 4 may load only train or validation samples; the locked test split "
            "is reserved for final evaluation"
        )
    root = Path(project_dir).resolve()
    samples: list[SplitSample] = []
    for row in manifest["scenes"]:
        if row.get("split") != split:
            continue
        scene_id = str(row["scene_id"])
        image_path = _safe_project_path(root, str(row["image_path"]))
        mask_path = _safe_project_path(root, str(row["mask_path"]))
        if not image_path.is_file():
            raise ValueError(f"{split} image is missing: {scene_id}")
        if not mask_path.is_file():
            raise ValueError(f"{split} mask is missing: {scene_id}")
        image_sha = str(row.get("image_sha256") or "")
        mask_sha = str(row.get("mask_sha256") or "")
        if verify_hashes:
            if sha256_file(image_path) != image_sha:
                raise ValueError(f"{split} image changed after split locking: {scene_id}")
            if sha256_file(mask_path) != mask_sha:
                raise ValueError(f"{split} mask changed after split locking: {scene_id}")
        samples.append(
            SplitSample(
                scene_id=scene_id,
                split=split,
                image_path=image_path,
                mask_path=mask_path,
                image_sha256=image_sha,
                mask_sha256=mask_sha,
            )
        )
    if not samples:
        raise ValueError(f"locked split contains no {split} samples")
    return samples


def _safe_project_path(project_dir: Path, value: str) -> Path:
    path = (project_dir / value).resolve()
    try:
        path.relative_to(project_dir)
    except ValueError as exc:
        raise ValueError(f"split manifest path escapes project directory: {value}") from exc
    return path


def letterbox_pair(
    image: Image.Image,
    mask: Image.Image,
    size: int,
) -> tuple[Image.Image, Image.Image]:
    if size < 64 or size % 16 != 0:
        raise ValueError("image size must be at least 64 and divisible by 16")
    image = ImageOps.exif_transpose(image).convert("RGB")
    mask = mask.convert("L")
    if image.size != mask.size:
        raise ValueError(
            f"image/mask dimensions differ before preprocessing: {image.size} vs {mask.size}"
        )
    width, height = image.size
    scale = min(size / width, size / height)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized_image = image.resize(
        (resized_width, resized_height), Image.Resampling.BILINEAR
    )
    resized_mask = mask.resize(
        (resized_width, resized_height), Image.Resampling.NEAREST
    )
    canvas_image = Image.new("RGB", (size, size), (127, 127, 127))
    canvas_mask = Image.new("L", (size, size), UNLABELLED_ID)
    left = (size - resized_width) // 2
    top = (size - resized_height) // 2
    canvas_image.paste(resized_image, (left, top))
    canvas_mask.paste(resized_mask, (left, top))
    return canvas_image, canvas_mask


def _validate_mask_values(mask: np.ndarray, scene_id: str) -> None:
    values = set(int(value) for value in np.unique(mask))
    invalid = values - set(SEMANTIC_LABEL_IDS) - {UNLABELLED_ID}
    if invalid:
        raise ValueError(f"{scene_id} mask contains invalid IDs: {sorted(invalid)}")


class RealVenueSegmentationDataset(Dataset):
    def __init__(
        self,
        samples: list[SplitSample],
        *,
        image_size: int = 256,
        augment: bool = False,
        seed: int = 260823,
    ) -> None:
        self.samples = list(samples)
        self.image_size = image_size
        self.augment = augment
        self.seed = seed
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.samples)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, str]:
        sample = self.samples[index]
        with Image.open(sample.image_path) as source_image:
            image = ImageOps.exif_transpose(source_image).convert("RGB")
        with Image.open(sample.mask_path) as source_mask:
            mask = source_mask.convert("L")
        image, mask = letterbox_pair(image, mask, self.image_size)

        if self.augment:
            rng = random.Random(self.seed + self.epoch * 100_003 + index * 97)
            if rng.random() < 0.5:
                image = ImageOps.mirror(image)
                mask = ImageOps.mirror(mask)
            image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.85, 1.15))
            image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.90, 1.10))

        image_array = np.asarray(image, dtype=np.float32) / 255.0
        # Fixed [-1, 1] scaling uses no outside/pretrained statistics.
        image_array = (image_array - 0.5) / 0.5
        mask_array = np.asarray(mask, dtype=np.uint8).copy()
        _validate_mask_values(mask_array, sample.scene_id)
        image_tensor = torch.from_numpy(image_array.transpose(2, 0, 1)).float()
        mask_tensor = torch.from_numpy(mask_array.astype(np.int64))
        return image_tensor, mask_tensor, sample.scene_id


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class UpBlock(nn.Module):
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int) -> None:
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, out_channels, 2, stride=2)
        self.conv = ConvBlock(out_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)
        if x.shape[-2:] != skip.shape[-2:]:
            x = nn.functional.interpolate(
                x, size=skip.shape[-2:], mode="bilinear", align_corners=False
            )
        return self.conv(torch.cat((skip, x), dim=1))


class BakeSmartVenueUNet(nn.Module):
    """Compact U-Net with random initialization and six semantic outputs."""

    def __init__(self, *, base_channels: int = 16, num_classes: int = NUM_CLASSES) -> None:
        super().__init__()
        if base_channels < 8:
            raise ValueError("base_channels must be at least 8")
        self.encoder1 = ConvBlock(3, base_channels)
        self.encoder2 = ConvBlock(base_channels, base_channels * 2)
        self.encoder3 = ConvBlock(base_channels * 2, base_channels * 4)
        self.encoder4 = ConvBlock(base_channels * 4, base_channels * 8)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(base_channels * 8, base_channels * 16)
        self.decoder4 = UpBlock(base_channels * 16, base_channels * 8, base_channels * 8)
        self.decoder3 = UpBlock(base_channels * 8, base_channels * 4, base_channels * 4)
        self.decoder2 = UpBlock(base_channels * 4, base_channels * 2, base_channels * 2)
        self.decoder1 = UpBlock(base_channels * 2, base_channels, base_channels)
        self.classifier = nn.Conv2d(base_channels, num_classes, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.encoder1(x)
        e2 = self.encoder2(self.pool(e1))
        e3 = self.encoder3(self.pool(e2))
        e4 = self.encoder4(self.pool(e3))
        bottleneck = self.bottleneck(self.pool(e4))
        x = self.decoder4(bottleneck, e4)
        x = self.decoder3(x, e3)
        x = self.decoder2(x, e2)
        x = self.decoder1(x, e1)
        return self.classifier(x)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def compute_train_class_weights(
    samples: Iterable[SplitSample],
    *,
    max_weight: float = 8.0,
) -> tuple[torch.Tensor, dict[str, int]]:
    counts = np.zeros(NUM_CLASSES, dtype=np.int64)
    for sample in samples:
        with Image.open(sample.mask_path) as source:
            mask = np.asarray(source.convert("L"), dtype=np.uint8)
        _validate_mask_values(mask, sample.scene_id)
        for class_id in SEMANTIC_LABEL_IDS:
            counts[class_id] += int(np.count_nonzero(mask == class_id))
    missing = [CLASS_NAMES[index] for index, count in enumerate(counts) if count == 0]
    if missing:
        raise ValueError(
            "training split has no labelled pixels for class(es): " + ", ".join(missing)
        )
    frequencies = counts / counts.sum()
    weights = 1.0 / np.sqrt(np.maximum(frequencies, 1e-12))
    weights /= np.mean(weights)
    weights = np.clip(weights, 0.25, max_weight)
    return (
        torch.tensor(weights, dtype=torch.float32),
        {CLASS_NAMES[index]: int(counts[index]) for index in range(NUM_CLASSES)},
    )


def dice_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    ignore_index: int = UNLABELLED_ID,
    epsilon: float = 1e-6,
) -> torch.Tensor:
    valid = targets != ignore_index
    safe_targets = targets.clone()
    safe_targets[~valid] = 0
    probabilities = torch.softmax(logits, dim=1)
    one_hot = nn.functional.one_hot(safe_targets, NUM_CLASSES).permute(0, 3, 1, 2).float()
    valid_mask = valid.unsqueeze(1).float()
    probabilities = probabilities * valid_mask
    one_hot = one_hot * valid_mask
    intersection = (probabilities * one_hot).sum(dim=(0, 2, 3))
    denominator = probabilities.sum(dim=(0, 2, 3)) + one_hot.sum(dim=(0, 2, 3))
    dice = (2.0 * intersection + epsilon) / (denominator + epsilon)
    return 1.0 - dice.mean()


class CombinedSegmentationLoss(nn.Module):
    def __init__(self, class_weights: torch.Tensor) -> None:
        super().__init__()
        self.register_buffer("class_weights", class_weights)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = nn.functional.cross_entropy(
            logits,
            targets,
            weight=self.class_weights,
            ignore_index=UNLABELLED_ID,
        )
        return 0.70 * ce + 0.30 * dice_loss(logits, targets)


class SegmentationConfusion:
    def __init__(self, num_classes: int = NUM_CLASSES) -> None:
        self.num_classes = num_classes
        self.matrix = np.zeros((num_classes, num_classes), dtype=np.int64)

    def update(self, targets: torch.Tensor, predictions: torch.Tensor) -> None:
        truth = targets.detach().cpu().numpy().reshape(-1)
        pred = predictions.detach().cpu().numpy().reshape(-1)
        valid = truth != UNLABELLED_ID
        truth = truth[valid]
        pred = pred[valid]
        if truth.size == 0:
            return
        encoded = truth * self.num_classes + pred
        counts = np.bincount(encoded, minlength=self.num_classes**2)
        self.matrix += counts.reshape(self.num_classes, self.num_classes)

    def metrics(self) -> dict[str, object]:
        total = int(self.matrix.sum())
        correct = int(np.trace(self.matrix))
        per_class: dict[str, dict[str, float | int | None]] = {}
        ious: list[float] = []
        for class_id, name in enumerate(CLASS_NAMES):
            tp = int(self.matrix[class_id, class_id])
            fp = int(self.matrix[:, class_id].sum() - tp)
            fn = int(self.matrix[class_id, :].sum() - tp)
            union = tp + fp + fn
            predicted = tp + fp
            actual = tp + fn
            iou = (tp / union) if union else None
            precision = (tp / predicted) if predicted else None
            recall = (tp / actual) if actual else None
            if iou is not None:
                ious.append(iou)
            per_class[name] = {
                "iou": None if iou is None else round(iou, 6),
                "precision": None if precision is None else round(precision, 6),
                "recall": None if recall is None else round(recall, 6),
                "support_pixels": actual,
            }
        return {
            "pixel_accuracy": round(correct / max(total, 1), 6),
            "mean_iou": round(float(np.mean(ious)) if ious else 0.0, 6),
            "per_class": per_class,
            "evaluated_pixels": total,
        }
