"""Train the v5 high-resolution Outlet detector on corrected development data.

Outlet masks are converted to boxes at load time. Training uses all full scenes
plus focused crops from positive scenes. Validation uses full scenes only. The
locked test split is never requested.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import torch
    from torch.utils.data import DataLoader, Dataset
    from torchvision.models.detection import (
        FasterRCNN_MobileNet_V3_Large_320_FPN_Weights,
        fasterrcnn_mobilenet_v3_large_320_fpn,
    )
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyTorch and torchvision are required for the v5 Outlet detector. "
        "Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR
from training.real_venue_segmentation import (
    SplitSample,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
)
from training.train_real_venue_segmentation_v2 import choose_device, set_seed, utc_now
from training.train_real_venue_segmentation_v5 import _validate_v5_manifest


DEFAULT_MANIFEST = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
    / "splits" / "v5_split_manifest.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_outlet_detector_v5"
DEFAULT_SEED = 260829
OUTLET_ID = 5


def outlet_boxes(labels: np.ndarray) -> np.ndarray:
    count, _components, stats, _centroids = cv2.connectedComponentsWithStats(
        (labels == OUTLET_ID).astype(np.uint8), connectivity=8
    )
    boxes: list[list[float]] = []
    for component in range(1, count):
        x = int(stats[component, cv2.CC_STAT_LEFT])
        y = int(stats[component, cv2.CC_STAT_TOP])
        width = int(stats[component, cv2.CC_STAT_WIDTH])
        height = int(stats[component, cv2.CC_STAT_HEIGHT])
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area <= 0 or width <= 0 or height <= 0:
            continue
        boxes.append([float(x), float(y), float(x + width), float(y + height)])
    if not boxes:
        return np.zeros((0, 4), dtype=np.float32)
    return np.asarray(boxes, dtype=np.float32)


def _load_pair(sample: SplitSample) -> tuple[Image.Image, Image.Image]:
    with Image.open(sample.image_path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    with Image.open(sample.mask_path) as opened:
        mask = opened.convert("L")
    if image.size != mask.size:
        raise ValueError(f"image/mask size mismatch: {sample.scene_id}")
    return image, mask


def _focus_crop(
    image: Image.Image,
    mask: Image.Image,
    *,
    rng: random.Random,
) -> tuple[Image.Image, Image.Image]:
    boxes = outlet_boxes(np.asarray(mask, dtype=np.uint8))
    if not len(boxes):
        return image, mask
    box = boxes[rng.randrange(len(boxes))]
    center_x = int(round((box[0] + box[2]) / 2))
    center_y = int(round((box[1] + box[3]) / 2))
    extent = max(int(box[2] - box[0]), int(box[3] - box[1]))
    width, height = image.size
    minimum_side = min(width, height)
    crop_size = max(128, int(round(extent * rng.uniform(7.0, 11.0))))
    crop_size = min(crop_size, max(128, int(round(minimum_side * 0.45))))
    crop_size = min(crop_size, minimum_side)
    jitter = max(2, crop_size // 12)
    center_x += rng.randint(-jitter, jitter)
    center_y += rng.randint(-jitter, jitter)
    left = max(0, min(center_x - crop_size // 2, width - crop_size))
    top = max(0, min(center_y - crop_size // 2, height - crop_size))
    crop_box = (left, top, left + crop_size, top + crop_size)
    return image.crop(crop_box), mask.crop(crop_box)


class OutletDetectionDataset(Dataset):
    def __init__(
        self,
        samples: list[SplitSample],
        *,
        training: bool,
        seed: int,
        focus_repeats: int = 8,
    ) -> None:
        self.samples = list(samples)
        self.training = training
        self.seed = seed
        self.epoch = 0
        self.views: list[tuple[int, bool, int]] = []
        self.positive_scene_count = 0
        for index, sample in enumerate(self.samples):
            self.views.append((index, False, 0))
            with Image.open(sample.mask_path) as opened:
                positive = bool(np.any(np.asarray(opened.convert("L")) == OUTLET_ID))
            if positive:
                self.positive_scene_count += 1
                if training:
                    for repeat in range(focus_repeats):
                        self.views.append((index, True, repeat))

    def __len__(self) -> int:
        return len(self.views)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, dict[str, torch.Tensor], str]:
        sample_index, focus, repeat = self.views[index]
        sample = self.samples[sample_index]
        rng = random.Random(self.seed + self.epoch * 1_000_003 + index * 10_007 + repeat)
        image, mask = _load_pair(sample)
        if focus:
            image, mask = _focus_crop(image, mask, rng=rng)
        if self.training and rng.random() < 0.5:
            image = ImageOps.mirror(image)
            mask = ImageOps.mirror(mask)
        if self.training:
            image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.85, 1.15))
            image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.90, 1.10))
        boxes_array = outlet_boxes(np.asarray(mask, dtype=np.uint8))
        boxes = torch.as_tensor(boxes_array, dtype=torch.float32)
        labels = torch.ones((len(boxes),), dtype=torch.int64)
        area = (
            (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            if len(boxes)
            else torch.zeros((0,), dtype=torch.float32)
        )
        image_array = np.asarray(image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(image_array.transpose(2, 0, 1)).float()
        target = {
            "boxes": boxes,
            "labels": labels,
            "image_id": torch.tensor([sample_index], dtype=torch.int64),
            "area": area,
            "iscrowd": torch.zeros((len(boxes),), dtype=torch.int64),
        }
        return tensor, target, sample.scene_id


def _collate(batch):
    return tuple(zip(*batch))


def _box_iou(box_a: torch.Tensor, box_b: torch.Tensor) -> float:
    left = max(float(box_a[0]), float(box_b[0]))
    top = max(float(box_a[1]), float(box_b[1]))
    right = min(float(box_a[2]), float(box_b[2]))
    bottom = min(float(box_a[3]), float(box_b[3]))
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = max(0.0, float(box_a[2] - box_a[0])) * max(0.0, float(box_a[3] - box_a[1]))
    area_b = max(0.0, float(box_b[2] - box_b[0])) * max(0.0, float(box_b[3] - box_b[1]))
    return intersection / max(area_a + area_b - intersection, 1e-9)


@torch.no_grad()
def validate(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    *,
    score_threshold: float,
    iou_threshold: float,
) -> dict[str, float | int]:
    model.eval()
    true_positive = false_positive = false_negative = 0
    for images, targets, _scene_ids in loader:
        outputs = model([image.to(device) for image in images])
        for output, target in zip(outputs, targets):
            scores = output["scores"].detach().cpu()
            predicted = output["boxes"].detach().cpu()[scores >= score_threshold]
            actual = target["boxes"]
            unmatched = set(range(len(actual)))
            for prediction in predicted:
                matches = sorted(
                    (
                        (_box_iou(prediction, actual[index]), index)
                        for index in unmatched
                    ),
                    reverse=True,
                )
                if matches and matches[0][0] >= iou_threshold:
                    true_positive += 1
                    unmatched.remove(matches[0][1])
                else:
                    false_positive += 1
            false_negative += len(unmatched)
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def train(args: argparse.Namespace) -> dict[str, object]:
    set_seed(args.seed)
    device = choose_device(args.device)
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    manifest = load_locked_split_manifest(
        manifest_path,
        project_dir=PROJECT_DIR,
        expected_dataset="real_v2_repaired",
    )
    _validate_v5_manifest(manifest)
    train_samples = samples_for_split(manifest, "train", project_dir=PROJECT_DIR)
    validation_samples = samples_for_split(manifest, "validation", project_dir=PROJECT_DIR)
    train_dataset = OutletDetectionDataset(
        train_samples,
        training=True,
        seed=args.seed,
        focus_repeats=args.focus_repeats,
    )
    validation_dataset = OutletDetectionDataset(
        validation_samples,
        training=False,
        seed=args.seed,
        focus_repeats=0,
    )
    if train_dataset.positive_scene_count < 1 or validation_dataset.positive_scene_count < 1:
        raise ValueError("v5 Outlet detector requires positive train and validation scenes")
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        collate_fn=_collate,
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=0,
        collate_fn=_collate,
    )

    print("Loading free pretrained Faster R-CNN/MobileNetV3 weights...")
    weights = FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT
    model = fasterrcnn_mobilenet_v3_large_320_fpn(
        weights=weights,
        min_size=args.minimum_image_size,
        max_size=args.maximum_image_size,
    )
    features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(features, 2)
    model.to(device)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=2, min_lr=1e-6
    )

    print("BakeSmart Step 4 v5 — Dedicated Outlet Detector")
    print(f"Device:                    {device}")
    print(f"Training scenes:           {len(train_samples)}")
    print(f"Training Outlet scenes:    {train_dataset.positive_scene_count}")
    print(f"Validation scenes:         {len(validation_samples)}")
    print(f"Validation Outlet scenes:  {validation_dataset.positive_scene_count}")
    print(f"Training views per epoch:  {len(train_dataset)}")
    print(f"Locked test used:          NO ({manifest['counts']['test']} remain untouched)")
    print("Training...\n")

    best_f1 = -math.inf
    best_epoch = 0
    best_metrics: dict[str, float | int] | None = None
    patience_left = args.patience
    history: list[dict[str, object]] = []
    best_path = output_dir / "best_model.pt"
    for epoch in range(1, args.epochs + 1):
        train_dataset.set_epoch(epoch)
        model.train()
        total_loss = 0.0
        batches = 0
        for images, targets, _scene_ids in train_loader:
            images_device = [image.to(device) for image in images]
            targets_device = [
                {key: value.to(device) for key, value in target.items()}
                for target in targets
            ]
            losses = model(images_device, targets_device)
            loss = sum(losses.values())
            if not torch.isfinite(loss):
                raise ValueError("Outlet detector loss became non-finite")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            if args.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
            total_loss += float(loss.detach().cpu())
            batches += 1
        metrics = validate(
            model,
            validation_loader,
            device,
            score_threshold=args.score_threshold,
            iou_threshold=args.iou_threshold,
        )
        f1 = float(metrics["f1"])
        scheduler.step(f1)
        improved = f1 > best_f1 + args.min_delta
        if improved:
            best_f1 = f1
            best_epoch = epoch
            best_metrics = metrics
            patience_left = args.patience
            best_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = best_path.with_suffix(".pt.part")
            torch.save(
                {
                    "schema_version": 5,
                    "model_name": "BakeSmartOutletDetector",
                    "architecture": "fasterrcnn_mobilenet_v3_large_320_fpn",
                    "pretrained": True,
                    "pretrained_weights": (
                        "FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT"
                    ),
                    "num_classes": 2,
                    "class_names": ["background", "outlet"],
                    "test_data_used": False,
                    "manifest_sha256": sha256_file(manifest_path),
                    "epoch": epoch,
                    "validation_metrics": metrics,
                    "model_state_dict": model.state_dict(),
                },
                temporary,
            )
            temporary.replace(best_path)
        else:
            patience_left -= 1
        average_loss = total_loss / max(batches, 1)
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(average_loss, 6),
                "validation": metrics,
                "learning_rate": float(optimizer.param_groups[0]["lr"]),
                "best_so_far": improved,
            }
        )
        star = " *BEST*" if improved else ""
        print(
            f"Epoch {epoch:03d}/{args.epochs} | loss {average_loss:.4f} | "
            f"precision {metrics['precision']:.4f} | recall {metrics['recall']:.4f} | "
            f"F1 {f1:.4f}{star}",
            flush=True,
        )
        if patience_left <= 0:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    if best_metrics is None or not best_path.is_file():
        raise ValueError("Outlet detector training finished without a valid checkpoint")
    report = {
        "schema_version": 5,
        "created_at_utc": utc_now(),
        "model_name": "BakeSmartOutletDetector",
        "architecture": "fasterrcnn_mobilenet_v3_large_320_fpn",
        "checkpoint": str(best_path.relative_to(PROJECT_DIR)),
        "checkpoint_sha256": sha256_file(best_path),
        "split_manifest": str(manifest_path.relative_to(PROJECT_DIR)),
        "split_manifest_sha256": sha256_file(manifest_path),
        "train_scene_count": len(train_samples),
        "validation_scene_count": len(validation_samples),
        "train_positive_scene_count": train_dataset.positive_scene_count,
        "validation_positive_scene_count": validation_dataset.positive_scene_count,
        "locked_test_scene_count": int(manifest["counts"]["test"]),
        "test_split_used": False,
        "best_epoch": best_epoch,
        "best_validation_metrics": best_metrics,
        "history": history,
        "production_ready": False,
        "next_step": "combine with the v5 room model after validation review",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_report.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    print("\nBest v5 Outlet detector validation result")
    print(f"Epoch:     {best_epoch}")
    print(f"Precision: {best_metrics['precision']:.4f}")
    print(f"Recall:    {best_metrics['recall']:.4f}")
    print(f"F1:        {best_metrics['f1']:.4f}")
    print(f"Checkpoint: {best_path.relative_to(PROJECT_DIR)}")
    print("Locked test set remains untouched.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--focus-repeats", type=int, default=8)
    parser.add_argument("--minimum-image-size", type=int, default=480)
    parser.add_argument("--maximum-image-size", type=int, default=768)
    parser.add_argument("--score-threshold", type=float, default=0.30)
    parser.add_argument("--iou-threshold", type=float, default=0.30)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser


def main() -> int:
    if "BAKESMART_TORCH_THREADS" in os.environ:
        torch.set_num_threads(max(1, int(os.environ["BAKESMART_TORCH_THREADS"])))
    try:
        train(build_parser().parse_args())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
