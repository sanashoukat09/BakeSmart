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
from dataclasses import dataclass
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
        "PyTorch and torchvision are required for the v5 object detector. "
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
MIN_COMPONENT_AREA = 4
MIN_BOX_SIDE = 4
CALIBRATION_SCORE_THRESHOLDS = (0.01, 0.03, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)


@dataclass(frozen=True)
class ObjectDetectorProfile:
    class_id: int
    class_key: str
    display_name: str
    model_name: str
    title: str
    minimum_training_scenes: int = 1
    adaptive_fine_tuning: bool = False
    forbidden_positive_scene_ids: tuple[str, ...] = ()


OUTLET_PROFILE = ObjectDetectorProfile(
    class_id=OUTLET_ID,
    class_key="outlet",
    display_name="Outlet",
    model_name="BakeSmartOutletDetector",
    title="BakeSmart Step 4 v5 — Dedicated Outlet Detector",
)


def object_boxes(labels: np.ndarray, class_id: int) -> np.ndarray:
    count, _components, stats, _centroids = cv2.connectedComponentsWithStats(
        (labels == class_id).astype(np.uint8), connectivity=8
    )
    boxes: list[list[float]] = []
    for component in range(1, count):
        x = int(stats[component, cv2.CC_STAT_LEFT])
        y = int(stats[component, cv2.CC_STAT_TOP])
        width = int(stats[component, cv2.CC_STAT_WIDTH])
        height = int(stats[component, cv2.CC_STAT_HEIGHT])
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < MIN_COMPONENT_AREA or width <= 0 or height <= 0:
            continue
        center_x = x + width / 2.0
        center_y = y + height / 2.0
        box_width = max(width, MIN_BOX_SIDE)
        box_height = max(height, MIN_BOX_SIDE)
        left = max(0.0, center_x - box_width / 2.0)
        top = max(0.0, center_y - box_height / 2.0)
        right = min(float(labels.shape[1]), left + box_width)
        bottom = min(float(labels.shape[0]), top + box_height)
        left = max(0.0, right - box_width)
        top = max(0.0, bottom - box_height)
        boxes.append([left, top, right, bottom])
    if not boxes:
        return np.zeros((0, 4), dtype=np.float32)
    return np.asarray(boxes, dtype=np.float32)


def outlet_boxes(labels: np.ndarray) -> np.ndarray:
    """Backward-compatible Outlet box helper used by tests and audits."""
    return object_boxes(labels, OUTLET_ID)


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
    class_id: int = OUTLET_ID,
) -> tuple[Image.Image, Image.Image]:
    boxes = object_boxes(np.asarray(mask, dtype=np.uint8), class_id)
    if not len(boxes):
        return image, mask
    box = boxes[rng.randrange(len(boxes))]
    center_x = int(round((box[0] + box[2]) / 2))
    center_y = int(round((box[1] + box[3]) / 2))
    extent = max(int(box[2] - box[0]), int(box[3] - box[1]))
    width, height = image.size
    minimum_side = min(width, height)
    if class_id == 2:
        crop_size = max(192, int(round(extent * rng.uniform(1.4, 2.2))))
        crop_size = min(crop_size, max(192, int(round(minimum_side * 0.85))))
    else:
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
        class_id: int = OUTLET_ID,
        display_name: str = "Outlet",
    ) -> None:
        self.samples = list(samples)
        self.training = training
        self.seed = seed
        self.epoch = 0
        self.class_id = class_id
        self.display_name = display_name
        self.views: list[tuple[int, bool, int]] = []
        self.positive_scene_count = 0
        self.positive_samples: list[SplitSample] = []
        for index, sample in enumerate(self.samples):
            self.views.append((index, False, 0))
            with Image.open(sample.mask_path) as opened:
                positive = bool(np.any(np.asarray(opened.convert("L")) == class_id))
            if positive:
                self.positive_scene_count += 1
                self.positive_samples.append(sample)
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
            image, mask = _focus_crop(
                image, mask, rng=rng, class_id=self.class_id
            )
        if self.training and rng.random() < 0.5:
            image = ImageOps.mirror(image)
            mask = ImageOps.mirror(mask)
        if self.training:
            image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.85, 1.15))
            image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.90, 1.10))
        boxes_array = object_boxes(
            np.asarray(mask, dtype=np.uint8), self.class_id
        )
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
        _validate_target(
            target,
            image.width,
            image.height,
            sample.scene_id,
            display_name=self.display_name,
        )
        return tensor, target, sample.scene_id


def _collate(batch):
    return tuple(zip(*batch))


def _validate_target(
    target: dict[str, torch.Tensor],
    width: int,
    height: int,
    scene_id: str,
    *,
    display_name: str = "Outlet",
) -> None:
    boxes = target["boxes"]
    if boxes.ndim != 2 or boxes.shape[1:] != (4,):
        raise ValueError(
            f"invalid {display_name} box shape for {scene_id}: {tuple(boxes.shape)}"
        )
    if not torch.isfinite(boxes).all():
        raise ValueError(f"non-finite {display_name} box for {scene_id}")
    if len(boxes):
        if not torch.all(boxes[:, 2] > boxes[:, 0]) or not torch.all(
            boxes[:, 3] > boxes[:, 1]
        ):
            raise ValueError(
                f"degenerate {display_name} box for {scene_id}: {boxes.tolist()}"
            )
        if (
            torch.any(boxes[:, 0] < 0)
            or torch.any(boxes[:, 1] < 0)
            or torch.any(boxes[:, 2] > width)
            or torch.any(boxes[:, 3] > height)
        ):
            raise ValueError(
                f"{display_name} box is outside the image for {scene_id}"
            )


def _box_iou(box_a: torch.Tensor, box_b: torch.Tensor) -> float:
    left = max(float(box_a[0]), float(box_b[0]))
    top = max(float(box_a[1]), float(box_b[1]))
    right = min(float(box_a[2]), float(box_b[2]))
    bottom = min(float(box_a[3]), float(box_b[3]))
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = max(0.0, float(box_a[2] - box_a[0])) * max(0.0, float(box_a[3] - box_a[1]))
    area_b = max(0.0, float(box_b[2] - box_b[0])) * max(0.0, float(box_b[3] - box_b[1]))
    return intersection / max(area_a + area_b - intersection, 1e-9)


def _model_parameters_are_finite(model: torch.nn.Module) -> bool:
    return all(torch.isfinite(parameter).all() for parameter in model.parameters())


def _score_predictions(
    predictions: list[tuple[torch.Tensor, torch.Tensor]],
    actual_boxes: list[torch.Tensor],
    *,
    score_threshold: float,
    iou_threshold: float,
) -> dict[str, object]:
    true_positive = false_positive = false_negative = 0
    for (boxes, scores), actual in zip(predictions, actual_boxes):
        predicted = boxes[scores >= score_threshold]
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


@torch.no_grad()
def validate(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    *,
    score_threshold: float,
    iou_threshold: float,
) -> dict[str, object]:
    model.eval()
    predictions: list[tuple[torch.Tensor, torch.Tensor]] = []
    actual_boxes: list[torch.Tensor] = []
    top_scores: list[float] = []
    best_ious: list[float] = []
    for images, targets, _scene_ids in loader:
        outputs = model([image.to(device) for image in images])
        for output, target in zip(outputs, targets):
            scores = output["scores"].detach().cpu()
            boxes = output["boxes"].detach().cpu()
            actual = target["boxes"]
            predictions.append((boxes, scores))
            actual_boxes.append(actual)
            if len(scores):
                top_scores.append(float(scores.max()))
            for ground_truth in actual:
                best_ious.append(
                    max((_box_iou(box, ground_truth) for box in boxes), default=0.0)
                )

    fixed = _score_predictions(
        predictions,
        actual_boxes,
        score_threshold=score_threshold,
        iou_threshold=iou_threshold,
    )
    threshold_metrics: dict[str, dict[str, object]] = {}
    for threshold in CALIBRATION_SCORE_THRESHOLDS:
        threshold_metrics[f"{threshold:.2f}"] = _score_predictions(
            predictions,
            actual_boxes,
            score_threshold=threshold,
            iou_threshold=iou_threshold,
        )
    best_threshold_key, calibrated = max(
        threshold_metrics.items(),
        key=lambda item: (
            float(item[1]["f1"]),
            float(item[1]["recall"]),
            float(item[0]),
        ),
    )
    return {
        **fixed,
        "fixed_score_threshold": score_threshold,
        "calibrated_score_threshold": float(best_threshold_key),
        "calibrated_precision": calibrated["precision"],
        "calibrated_recall": calibrated["recall"],
        "calibrated_f1": calibrated["f1"],
        "maximum_score": round(max(top_scores, default=0.0), 6),
        "mean_top_score": round(sum(top_scores) / max(len(top_scores), 1), 6),
        "mean_best_iou": round(sum(best_ious) / max(len(best_ious), 1), 6),
        "threshold_metrics": threshold_metrics,
    }


def train(
    args: argparse.Namespace,
    *,
    profile: ObjectDetectorProfile = OUTLET_PROFILE,
) -> dict[str, object]:
    set_seed(args.seed)
    device = choose_device(args.device)
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    best_path = output_dir / "best_model.pt"
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
        class_id=profile.class_id,
        display_name=profile.display_name,
    )
    validation_dataset = OutletDetectionDataset(
        validation_samples,
        training=False,
        seed=args.seed,
        focus_repeats=0,
        class_id=profile.class_id,
        display_name=profile.display_name,
    )
    forbidden = sorted(
        set(profile.forbidden_positive_scene_ids)
        & {
            sample.scene_id
            for sample in train_dataset.positive_samples
            + validation_dataset.positive_samples
        }
    )
    if forbidden:
        raise ValueError(
            f"invalid {profile.display_name} detector labels remain in "
            f"{', '.join(forbidden)}; run: "
            "python -m training.correct_real_v2_door_labels_v6"
        )
    if (
        train_dataset.positive_scene_count < profile.minimum_training_scenes
        or validation_dataset.positive_scene_count < 1
    ):
        raise ValueError(
            f"v5 {profile.display_name} detector requires at least "
            f"{profile.minimum_training_scenes} positive training scene(s) and one "
            "positive validation scene"
        )
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
    probe_loader = None
    if profile.adaptive_fine_tuning:
        probe_samples = train_dataset.positive_samples[: args.probe_scenes]
        probe_dataset = OutletDetectionDataset(
            probe_samples,
            training=False,
            seed=args.seed,
            focus_repeats=0,
            class_id=profile.class_id,
            display_name=profile.display_name,
        )
        probe_loader = DataLoader(
            probe_dataset,
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
        box_score_thresh=(
            min(CALIBRATION_SCORE_THRESHOLDS)
            if profile.adaptive_fine_tuning
            else 0.05
        ),
    )
    features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(features, 2)
    model.to(device)
    resume_payload: dict[str, object] | None = None
    starting_epoch = 0
    if args.resume_checkpoint:
        resume_path = Path(args.resume_checkpoint).resolve()
        if not resume_path.is_file():
            raise ValueError(f"resume checkpoint is missing: {resume_path}")
        loaded = torch.load(resume_path, map_location=device, weights_only=False)
        if not isinstance(loaded, dict):
            raise ValueError("resume checkpoint root must be a dictionary")
        if loaded.get("model_name") != profile.model_name:
            raise ValueError(
                f"resume checkpoint model mismatch: {loaded.get('model_name')!r}"
            )
        if loaded.get("test_data_used") is not False:
            raise ValueError("resume checkpoint must confirm test_data_used=false")
        if loaded.get("manifest_sha256") != sha256_file(manifest_path):
            raise ValueError("resume checkpoint does not match the current split manifest")
        state = loaded.get("model_state_dict")
        if not isinstance(state, dict):
            raise ValueError("resume checkpoint has no model state")
        model.load_state_dict(state, strict=True)
        if not _model_parameters_are_finite(model):
            raise ValueError("resume checkpoint contains non-finite model parameters")
        starting_epoch = int(loaded.get("epoch") or 0)
        if starting_epoch < 1 or starting_epoch >= args.epochs:
            raise ValueError(
                f"resume epoch {starting_epoch} must be below target epoch {args.epochs}"
            )
        resume_payload = loaded
    if profile.adaptive_fine_tuning:
        # TorchVision's pretrained factory already freezes early MobileNet
        # stages. Warm up the new predictor, then adapt every remaining
        # trainable detector layer as in the official fine-tuning recipe.
        adaptation_parameters = [
            parameter
            for name, parameter in model.named_parameters()
            if parameter.requires_grad and not name.startswith("roi_heads.box_predictor.")
        ]
        predictor_parameters = list(model.roi_heads.box_predictor.parameters())
        if resume_payload is None:
            for parameter in adaptation_parameters:
                parameter.requires_grad = False
        optimizer = torch.optim.SGD(
            [
                {
                    "params": adaptation_parameters,
                    "lr": args.rpn_learning_rate,
                    "name": "adaptation",
                },
                {
                    "params": predictor_parameters,
                    "lr": args.learning_rate,
                    "name": "predictor",
                },
            ],
            momentum=args.momentum,
            weight_decay=args.weight_decay,
        )
    else:
        # Retain the stabilized Outlet behavior for backward compatibility.
        adaptation_parameters = []
        for parameter in model.parameters():
            parameter.requires_grad = False
        for parameter in model.rpn.parameters():
            parameter.requires_grad = True
        for parameter in model.roi_heads.box_predictor.parameters():
            parameter.requires_grad = True
        optimizer = torch.optim.AdamW(
            [
                {"params": model.rpn.parameters(), "lr": args.rpn_learning_rate},
                {
                    "params": model.roi_heads.box_predictor.parameters(),
                    "lr": args.learning_rate,
                },
            ],
            weight_decay=args.weight_decay,
        )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=2, min_lr=1e-6
    )

    print(profile.title)
    print(f"Device:                    {device}")
    print(f"Training scenes:           {len(train_samples)}")
    print(
        f"Training {profile.display_name} scenes:    "
        f"{train_dataset.positive_scene_count}"
    )
    print(f"Validation scenes:         {len(validation_samples)}")
    print(
        f"Validation {profile.display_name} scenes:  "
        f"{validation_dataset.positive_scene_count}"
    )
    print(f"Training views per epoch:  {len(train_dataset)}")
    if profile.adaptive_fine_tuning:
        print(
            f"Fine-tuning:               new {profile.display_name} predictor for "
            f"{args.warmup_epochs} warmup epoch(s), then pretrained detector layers"
        )
        print(
            "Validation:                confidence sweep 0.01-0.50 + fixed F1@0.30"
        )
        print(
            f"Failure guard:             training-positive probe at epoch "
            f"{args.probe_epoch}"
        )
        if resume_payload is not None:
            print(
                f"Resume:                    valid epoch {starting_epoch} checkpoint; "
                "warmup already completed"
            )
    else:
        print(
            f"Fine-tuning:               RPN + new {profile.display_name} predictor "
            "(backbone frozen)"
        )
    print(f"Locked test used:          NO ({manifest['counts']['test']} remain untouched)")
    print("Training...\n")

    if resume_payload is None:
        best_f1 = -math.inf
        best_epoch = 0
        best_metrics: dict[str, object] | None = None
    else:
        loaded_metrics = resume_payload.get("validation_metrics")
        if not isinstance(loaded_metrics, dict):
            raise ValueError("resume checkpoint has no validation metrics")
        best_metrics = loaded_metrics
        best_epoch = starting_epoch
        best_f1 = float(
            best_metrics.get(
                "calibrated_f1" if profile.adaptive_fine_tuning else "f1",
                -math.inf,
            )
        )
    patience_left = args.patience
    history: list[dict[str, object]] = []
    skipped_nonfinite_batches = 0
    for epoch in range(starting_epoch + 1, args.epochs + 1):
        if (
            profile.adaptive_fine_tuning
            and resume_payload is None
            and epoch == args.warmup_epochs + 1
        ):
            for parameter in adaptation_parameters:
                parameter.requires_grad = True
            print("Pretrained detector layers unfrozen for low-rate adaptation.")
        train_dataset.set_epoch(epoch)
        model.train()
        if not profile.adaptive_fine_tuning:
            model.backbone.eval()
            model.roi_heads.box_head.eval()
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
                details = ", ".join(
                    f"{name}={float(value.detach().cpu()):.6g}"
                    for name, value in losses.items()
                )
                if not _model_parameters_are_finite(model):
                    raise ValueError(
                        f"{profile.display_name} detector parameters became non-finite "
                        f"before {', '.join(_scene_ids)} ({details}); resume from the "
                        "last valid checkpoint with the v6 resume command"
                    )
                skipped_nonfinite_batches += 1
                optimizer.zero_grad(set_to_none=True)
                print(
                    f"WARNING: skipped non-finite batch {', '.join(_scene_ids)} "
                    f"({details})",
                    flush=True,
                )
                if skipped_nonfinite_batches > args.max_nonfinite_skips:
                    raise ValueError(
                        f"more than {args.max_nonfinite_skips} non-finite batches were "
                        "encountered; stopping safely"
                    )
                continue
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            if args.grad_clip > 0:
                gradient_norm = torch.nn.utils.clip_grad_norm_(
                    model.parameters(), args.grad_clip
                )
                if not torch.isfinite(gradient_norm):
                    skipped_nonfinite_batches += 1
                    optimizer.zero_grad(set_to_none=True)
                    print(
                        f"WARNING: skipped non-finite gradients for "
                        f"{', '.join(_scene_ids)}",
                        flush=True,
                    )
                    if skipped_nonfinite_batches > args.max_nonfinite_skips:
                        raise ValueError(
                            f"more than {args.max_nonfinite_skips} non-finite batches "
                            "were encountered; stopping safely"
                        )
                    continue
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
        fixed_f1 = float(metrics["f1"])
        calibrated_f1 = float(metrics["calibrated_f1"])
        selection_f1 = (
            calibrated_f1 if profile.adaptive_fine_tuning else fixed_f1
        )
        scheduler.step(selection_f1)
        improved = selection_f1 > best_f1 + args.min_delta
        if improved:
            best_f1 = selection_f1
            best_epoch = epoch
            best_metrics = metrics
            patience_left = args.patience
            best_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = best_path.with_suffix(".pt.part")
            torch.save(
                {
                    "schema_version": 6 if profile.adaptive_fine_tuning else 5,
                    "model_name": profile.model_name,
                    "architecture": "fasterrcnn_mobilenet_v3_large_320_fpn",
                    "pretrained": True,
                    "pretrained_weights": (
                        "FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT"
                    ),
                    "num_classes": 2,
                    "class_names": ["background", profile.class_key],
                    "test_data_used": False,
                    "manifest_sha256": sha256_file(manifest_path),
                    "epoch": epoch,
                    "validation_metrics": metrics,
                    "model_selection_metric": (
                        "calibrated_f1" if profile.adaptive_fine_tuning else "f1"
                    ),
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
                "rpn_learning_rate": float(optimizer.param_groups[0]["lr"]),
                "predictor_learning_rate": float(optimizer.param_groups[1]["lr"]),
                "best_so_far": improved,
                "nonfinite_batches_skipped_total": skipped_nonfinite_batches,
            }
        )
        star = " *BEST*" if improved else ""
        if profile.adaptive_fine_tuning:
            print(
                f"Epoch {epoch:03d}/{args.epochs} | loss {average_loss:.4f} | "
                f"F1@.30 {fixed_f1:.4f} | bestF1 {calibrated_f1:.4f} "
                f"@{metrics['calibrated_score_threshold']:.2f} | "
                f"max score {metrics['maximum_score']:.3f} | "
                f"best IoU {metrics['mean_best_iou']:.3f}{star}",
                flush=True,
            )
        else:
            print(
                f"Epoch {epoch:03d}/{args.epochs} | loss {average_loss:.4f} | "
                f"precision {metrics['precision']:.4f} | recall {metrics['recall']:.4f} | "
                f"F1 {fixed_f1:.4f}{star}",
                flush=True,
            )
        if (
            profile.adaptive_fine_tuning
            and probe_loader is not None
            and epoch == args.probe_epoch
        ):
            probe = validate(
                model,
                probe_loader,
                device,
                score_threshold=args.score_threshold,
                iou_threshold=args.iou_threshold,
            )
            print(
                f"Training-positive probe | bestF1 {probe['calibrated_f1']:.4f} "
                f"@{probe['calibrated_score_threshold']:.2f} | "
                f"max score {probe['maximum_score']:.3f} | "
                f"best IoU {probe['mean_best_iou']:.3f}"
            )
            if float(probe["calibrated_f1"]) <= 0.0:
                raise ValueError(
                    f"{profile.display_name} detector failed its epoch-"
                    f"{args.probe_epoch} training-positive probe; stopping before "
                    "a long zero-result run. Check the printed score and IoU diagnostics."
                )
        if patience_left <= 0:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    if best_metrics is None or not best_path.is_file():
        raise ValueError(
            f"{profile.display_name} detector training finished without a valid checkpoint"
        )
    report = {
        "schema_version": 6 if profile.adaptive_fine_tuning else 5,
        "created_at_utc": utc_now(),
        "model_name": profile.model_name,
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
        "resumed_from_epoch": starting_epoch if resume_payload is not None else None,
        "nonfinite_batches_skipped": skipped_nonfinite_batches,
        "best_validation_metrics": best_metrics,
        "history": history,
        "production_ready": False,
        "detected_class": profile.class_key,
        "model_selection_metric": (
            "calibrated_f1" if profile.adaptive_fine_tuning else "f1"
        ),
        "next_step": "combine with the v5 room model after validation review",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_report.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    detector_version = "v6" if profile.adaptive_fine_tuning else "v5"
    print(f"\nBest {detector_version} {profile.display_name} detector validation result")
    print(f"Epoch:     {best_epoch}")
    print(f"Precision: {best_metrics['precision']:.4f}")
    print(f"Recall:    {best_metrics['recall']:.4f}")
    print(f"F1:        {best_metrics['f1']:.4f}")
    if profile.adaptive_fine_tuning:
        print(
            f"Best calibrated F1: {best_metrics['calibrated_f1']:.4f} "
            f"at score >= {best_metrics['calibrated_score_threshold']:.2f}"
        )
        print(f"Maximum score:      {best_metrics['maximum_score']:.4f}")
        print(f"Mean best IoU:      {best_metrics['mean_best_iou']:.4f}")
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
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--rpn-learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--momentum", type=float, default=0.9)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--focus-repeats", type=int, default=8)
    parser.add_argument("--minimum-image-size", type=int, default=480)
    parser.add_argument("--maximum-image-size", type=int, default=768)
    parser.add_argument("--score-threshold", type=float, default=0.30)
    parser.add_argument("--iou-threshold", type=float, default=0.30)
    parser.add_argument("--warmup-epochs", type=int, default=2)
    parser.add_argument("--probe-epoch", type=int, default=5)
    parser.add_argument("--probe-scenes", type=int, default=3)
    parser.add_argument("--resume-checkpoint")
    parser.add_argument("--max-nonfinite-skips", type=int, default=3)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser


def main() -> int:
    if "BAKESMART_TORCH_THREADS" in os.environ:
        torch.set_num_threads(max(1, int(os.environ["BAKESMART_TORCH_THREADS"])))
    try:
        train(build_parser().parse_args(), profile=OUTLET_PROFILE)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
