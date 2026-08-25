"""Rare-class focused training helpers for BakeSmart venue segmentation v2.

The v1 model established a real-photo baseline but Door and Outlet had zero
validation IoU. This module keeps the same six-class U-Net and locked split,
then improves the *training views* only:

* every training scene still contributes a full-room view;
* random square crops preserve local detail;
* Door-containing scenes add Door-focused crops;
* Outlet-containing scenes add more strongly oversampled Outlet-focused crops;
* validation remains deterministic and is evaluated with tiled inference at a
  higher resolution so small classes are not reduced to only a handful of
  pixels.

No pretrained weights are used and the locked test split is never loaded here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import torch
    from torch import nn
    from torch.utils.data import Dataset
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyTorch is required for Step 4 v2. Install project requirements with: "
        "pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import UNLABELLED_ID
from training.real_venue_segmentation import (
    CLASS_NAMES,
    NUM_CLASSES,
    SplitSample,
    _validate_mask_values,
)


DOOR_ID = 2
OUTLET_ID = 5


@dataclass(frozen=True)
class TrainingView:
    sample_index: int
    mode: str
    target_class: int | None = None
    repeat_index: int = 0


def _load_pair(sample: SplitSample) -> tuple[Image.Image, Image.Image]:
    with Image.open(sample.image_path) as source_image:
        image = ImageOps.exif_transpose(source_image).convert("RGB")
    with Image.open(sample.mask_path) as source_mask:
        mask = source_mask.convert("L")
    if image.size != mask.size:
        raise ValueError(
            f"image/mask dimensions differ for {sample.scene_id}: {image.size} vs {mask.size}"
        )
    _validate_mask_values(np.asarray(mask, dtype=np.uint8), sample.scene_id)
    return image, mask


def _square_crop_box(
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    crop_size: int,
) -> tuple[int, int, int, int]:
    crop_size = max(16, min(int(crop_size), width, height))
    left = center_x - crop_size // 2
    top = center_y - crop_size // 2
    left = max(0, min(left, width - crop_size))
    top = max(0, min(top, height - crop_size))
    return left, top, left + crop_size, top + crop_size


def _focus_crop(
    image: Image.Image,
    mask: Image.Image,
    *,
    class_id: int,
    rng: random.Random,
) -> tuple[Image.Image, Image.Image]:
    labels = np.asarray(mask, dtype=np.uint8)
    ys, xs = np.where(labels == class_id)
    if xs.size == 0:
        return _random_crop(image, mask, rng=rng)

    pick = rng.randrange(xs.size)
    center_x = int(xs[pick])
    center_y = int(ys[pick])
    width, height = image.size
    min_side = min(width, height)

    bbox_width = int(xs.max() - xs.min() + 1)
    bbox_height = int(ys.max() - ys.min() + 1)
    object_extent = max(bbox_width, bbox_height)
    if class_id == OUTLET_ID:
        # Keep a small outlet visibly large while retaining nearby wall/floor
        # context. Jittering scale prevents memorizing one exact crop.
        minimum = max(96, int(round(min_side * 0.12)))
        crop_size = max(minimum, int(round(object_extent * rng.uniform(5.0, 8.0))))
        crop_size = min(crop_size, max(minimum, int(round(min_side * 0.42))))
    else:
        minimum = max(160, int(round(min_side * 0.28)))
        crop_size = max(minimum, int(round(object_extent * rng.uniform(1.35, 2.0))))
        crop_size = min(crop_size, max(minimum, int(round(min_side * 0.72))))

    jitter = max(2, crop_size // 10)
    center_x += rng.randint(-jitter, jitter)
    center_y += rng.randint(-jitter, jitter)
    box = _square_crop_box(width, height, center_x, center_y, crop_size)
    return image.crop(box), mask.crop(box)


def _random_crop(
    image: Image.Image,
    mask: Image.Image,
    *,
    rng: random.Random,
) -> tuple[Image.Image, Image.Image]:
    width, height = image.size
    min_side = min(width, height)
    crop_size = int(round(min_side * rng.uniform(0.48, 0.88)))
    crop_size = max(64, min(crop_size, min_side))
    left = rng.randint(0, max(0, width - crop_size))
    top = rng.randint(0, max(0, height - crop_size))
    box = (left, top, left + crop_size, top + crop_size)
    return image.crop(box), mask.crop(box)


def _resize_pair(
    image: Image.Image,
    mask: Image.Image,
    size: int,
) -> tuple[Image.Image, Image.Image]:
    if size < 64 or size % 16 != 0:
        raise ValueError("training crop size must be at least 64 and divisible by 16")
    return (
        image.resize((size, size), Image.Resampling.BILINEAR),
        mask.resize((size, size), Image.Resampling.NEAREST),
    )


def _to_tensors(
    image: Image.Image,
    mask: Image.Image,
    scene_id: str,
    *,
    normalization: str = "half",
) -> tuple[torch.Tensor, torch.Tensor]:
    image_array = np.asarray(image, dtype=np.float32) / 255.0
    if normalization == "half":
        image_array = (image_array - 0.5) / 0.5
    elif normalization == "imagenet":
        image_array = (
            image_array - np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        ) / np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
    else:
        raise ValueError(f"unsupported image normalization: {normalization}")
    mask_array = np.asarray(mask, dtype=np.uint8).copy()
    _validate_mask_values(mask_array, scene_id)
    return (
        torch.from_numpy(image_array.transpose(2, 0, 1)).float(),
        torch.from_numpy(mask_array.astype(np.int64)),
    )


class RareClassTrainingDataset(Dataset):
    """Full-room + local + rare-class crops built only from training scenes."""

    def __init__(
        self,
        samples: list[SplitSample],
        *,
        image_size: int = 256,
        seed: int = 260823,
        random_crops_per_scene: int = 1,
        door_crops_per_scene: int = 2,
        outlet_crops_per_scene: int = 5,
        normalization: str = "half",
    ) -> None:
        self.samples = list(samples)
        self.image_size = image_size
        self.seed = seed
        self.epoch = 0
        self.normalization = normalization
        self.views: list[TrainingView] = []
        self.presence = {"door_scenes": 0, "outlet_scenes": 0}

        for sample_index, sample in enumerate(self.samples):
            with Image.open(sample.mask_path) as source:
                labels = np.asarray(source.convert("L"), dtype=np.uint8)
            _validate_mask_values(labels, sample.scene_id)
            has_door = bool(np.any(labels == DOOR_ID))
            has_outlet = bool(np.any(labels == OUTLET_ID))
            if has_door:
                self.presence["door_scenes"] += 1
            if has_outlet:
                self.presence["outlet_scenes"] += 1

            self.views.append(TrainingView(sample_index, "full"))
            for repeat in range(random_crops_per_scene):
                self.views.append(TrainingView(sample_index, "random", repeat_index=repeat))
            if has_door:
                for repeat in range(door_crops_per_scene):
                    self.views.append(
                        TrainingView(
                            sample_index,
                            "focus",
                            target_class=DOOR_ID,
                            repeat_index=repeat,
                        )
                    )
            if has_outlet:
                for repeat in range(outlet_crops_per_scene):
                    self.views.append(
                        TrainingView(
                            sample_index,
                            "focus",
                            target_class=OUTLET_ID,
                            repeat_index=repeat,
                        )
                    )

        if not self.views:
            raise ValueError("rare-class training dataset is empty")

    def __len__(self) -> int:
        return len(self.views)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, str]:
        view = self.views[index]
        sample = self.samples[view.sample_index]
        rng = random.Random(
            self.seed
            + self.epoch * 1_000_003
            + index * 10_007
            + view.repeat_index * 101
        )
        image, mask = _load_pair(sample)
        if view.mode == "random":
            image, mask = _random_crop(image, mask, rng=rng)
        elif view.mode == "focus":
            assert view.target_class is not None
            image, mask = _focus_crop(
                image,
                mask,
                class_id=view.target_class,
                rng=rng,
            )
        elif view.mode != "full":
            raise ValueError(f"unsupported training view: {view.mode}")

        image, mask = _resize_pair(image, mask, self.image_size)
        if rng.random() < 0.5:
            image = ImageOps.mirror(image)
            mask = ImageOps.mirror(mask)
        image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.82, 1.18))
        image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.88, 1.12))
        return (
            *_to_tensors(
                image,
                mask,
                sample.scene_id,
                normalization=self.normalization,
            ),
            sample.scene_id,
        )


class TiledValidationDataset(Dataset):
    """Deterministic higher-resolution validation images; no augmentation."""

    def __init__(
        self,
        samples: list[SplitSample],
        *,
        canvas_size: int = 512,
        normalization: str = "half",
    ) -> None:
        if canvas_size < 256 or canvas_size % 16 != 0:
            raise ValueError("validation canvas size must be >=256 and divisible by 16")
        self.samples = list(samples)
        self.canvas_size = canvas_size
        self.normalization = normalization

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, str]:
        sample = self.samples[index]
        image, mask = _load_pair(sample)
        image, mask = _letterbox_high_resolution(image, mask, self.canvas_size)
        return (
            *_to_tensors(
                image,
                mask,
                sample.scene_id,
                normalization=self.normalization,
            ),
            sample.scene_id,
        )


def _letterbox_high_resolution(
    image: Image.Image,
    mask: Image.Image,
    size: int,
) -> tuple[Image.Image, Image.Image]:
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
    image_canvas = Image.new("RGB", (size, size), (127, 127, 127))
    mask_canvas = Image.new("L", (size, size), UNLABELLED_ID)
    left = (size - resized_width) // 2
    top = (size - resized_height) // 2
    image_canvas.paste(resized_image, (left, top))
    mask_canvas.paste(resized_mask, (left, top))
    return image_canvas, mask_canvas


def tile_positions(full_size: int, tile_size: int, stride: int) -> list[int]:
    if tile_size > full_size:
        raise ValueError("tile size cannot exceed validation canvas size")
    if stride <= 0 or stride > tile_size:
        raise ValueError("tile stride must be >0 and <= tile size")
    positions = list(range(0, full_size - tile_size + 1, stride))
    last = full_size - tile_size
    if not positions or positions[-1] != last:
        positions.append(last)
    return positions


@torch.no_grad()
def tiled_logits(
    model: nn.Module,
    image: torch.Tensor,
    *,
    tile_size: int = 256,
    stride: int = 192,
) -> torch.Tensor:
    """Average overlapping logits over one BCHW validation image."""
    if image.ndim != 4 or image.shape[0] != 1:
        raise ValueError("tiled validation expects one BCHW image at a time")
    _, _, height, width = image.shape
    if height != width:
        raise ValueError("tiled validation expects a square canvas")
    ys = tile_positions(height, tile_size, stride)
    xs = tile_positions(width, tile_size, stride)
    accumulated = torch.zeros(
        (1, NUM_CLASSES, height, width),
        dtype=image.dtype,
        device=image.device,
    )
    counts = torch.zeros(
        (1, 1, height, width),
        dtype=image.dtype,
        device=image.device,
    )
    for top in ys:
        for left in xs:
            tile = image[..., top : top + tile_size, left : left + tile_size]
            logits = model(tile)
            accumulated[..., top : top + tile_size, left : left + tile_size] += logits
            counts[..., top : top + tile_size, left : left + tile_size] += 1.0
    return accumulated / counts.clamp_min(1.0)


def boosted_class_weights(
    base_weights: torch.Tensor,
    *,
    door_multiplier: float = 1.8,
    outlet_multiplier: float = 3.5,
    max_weight: float = 12.0,
) -> torch.Tensor:
    """Strengthen rare-class loss while keeping the mean scale near one."""
    weights = base_weights.detach().clone().float()
    weights[DOOR_ID] *= door_multiplier
    weights[OUTLET_ID] *= outlet_multiplier
    weights /= weights.mean().clamp_min(1e-6)
    return weights.clamp(0.20, max_weight)


class RareAwareSegmentationLoss(nn.Module):
    """Weighted CE + Dice with slightly more weight on overlap quality."""

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
        valid = targets != UNLABELLED_ID
        safe_targets = targets.clone()
        safe_targets[~valid] = 0
        probabilities = torch.softmax(logits, dim=1)
        one_hot = nn.functional.one_hot(safe_targets, NUM_CLASSES).permute(0, 3, 1, 2).float()
        valid_mask = valid.unsqueeze(1).float()
        probabilities = probabilities * valid_mask
        one_hot = one_hot * valid_mask
        intersection = (probabilities * one_hot).sum(dim=(0, 2, 3))
        denominator = probabilities.sum(dim=(0, 2, 3)) + one_hot.sum(dim=(0, 2, 3))
        dice_per_class = (2.0 * intersection + 1e-6) / (denominator + 1e-6)
        # Rare classes receive additional influence on the Dice component too.
        dice_weights = self.class_weights / self.class_weights.sum().clamp_min(1e-6)
        dice = (dice_per_class * dice_weights).sum()
        return 0.60 * ce + 0.40 * (1.0 - dice)


def training_view_summary(dataset: RareClassTrainingDataset) -> dict[str, int]:
    counts = {"full": 0, "random": 0, "door_focus": 0, "outlet_focus": 0}
    for view in dataset.views:
        if view.mode == "full":
            counts["full"] += 1
        elif view.mode == "random":
            counts["random"] += 1
        elif view.target_class == DOOR_ID:
            counts["door_focus"] += 1
        elif view.target_class == OUTLET_ID:
            counts["outlet_focus"] += 1
    return counts
