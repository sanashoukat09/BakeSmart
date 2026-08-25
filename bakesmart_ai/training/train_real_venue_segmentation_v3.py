"""Train BakeSmart venue segmentation v3 with balanced rare-class emphasis.

v3 keeps the locked Step-3 split and fresh random initialization, but corrects
v2's over-emphasis on Outlet. It uses fewer Outlet-focused crops, moderate class
weights, and selects the best checkpoint using a validation score dominated by
overall mean IoU with smaller Door and Outlet bonuses.

The 9 locked test scenes are never loaded by this trainer.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyTorch is required for Step 4 v3. Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR, UNLABELLED_ID
from training.real_venue_segmentation import (
    BakeSmartVenueUNet,
    CLASS_NAMES,
    NUM_CLASSES,
    compute_train_class_weights,
    count_parameters,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
)
from training.real_venue_segmentation_v2 import (
    DOOR_ID,
    OUTLET_ID,
    RareClassTrainingDataset,
    TiledValidationDataset,
    training_view_summary,
)
from training.train_real_venue_segmentation_v2 import (
    choose_device,
    run_train_epoch,
    run_validation,
    set_seed,
    utc_now,
)


DEFAULT_MANIFEST = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "raw"
    / "real_v2"
    / "splits"
    / "split_manifest.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_real_v3"
DEFAULT_SEED = 260825


@dataclass(frozen=True)
class TrainingProfile:
    title: str = "BakeSmart Step 4 v3 — Balanced Rare-Class Venue Segmentation"
    expected_dataset: str = "real_v2"
    schema_version: int = 3
    training_variant: str = "balanced_rare_class_crops_v3"
    training_data: str = "reviewed_real_v2_train_split_only"
    validation_data: str = "reviewed_real_v2_validation_split_only"
    result_heading: str = "Best v3 validation result"
    prior_outputs_message: str = "v1 and v2 outputs remain untouched."
    next_step: str = "compare v3 with v1/v2 on validation before locked-test evaluation"


def balanced_class_weights(
    base_weights: torch.Tensor,
    *,
    door_multiplier: float = 1.20,
    outlet_multiplier: float = 1.15,
    min_weight: float = 0.25,
    max_weight: float = 4.0,
) -> torch.Tensor:
    """Moderately emphasize rare classes without letting Outlet dominate."""
    if door_multiplier <= 0 or outlet_multiplier <= 0:
        raise ValueError("class-weight multipliers must be positive")
    if min_weight <= 0 or max_weight < min_weight:
        raise ValueError("invalid class-weight bounds")
    weights = base_weights.detach().clone().float()
    weights[DOOR_ID] *= door_multiplier
    weights[OUTLET_ID] *= outlet_multiplier
    weights /= weights.mean().clamp_min(1e-6)
    return weights.clamp(min_weight, max_weight)


class BalancedRareAwareLoss(nn.Module):
    """Moderate weighted CE + weighted Dice for v3."""

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
        one_hot = nn.functional.one_hot(
            safe_targets, NUM_CLASSES
        ).permute(0, 3, 1, 2).float()
        valid_mask = valid.unsqueeze(1).float()
        probabilities = probabilities * valid_mask
        one_hot = one_hot * valid_mask
        intersection = (probabilities * one_hot).sum(dim=(0, 2, 3))
        denominator = (
            probabilities.sum(dim=(0, 2, 3))
            + one_hot.sum(dim=(0, 2, 3))
        )
        dice_per_class = (2.0 * intersection + 1e-6) / (denominator + 1e-6)
        dice_weights = self.class_weights / self.class_weights.sum().clamp_min(1e-6)
        weighted_dice = (dice_per_class * dice_weights).sum()
        return 0.65 * ce + 0.35 * (1.0 - weighted_dice)


def balanced_validation_score(
    metrics: dict[str, object],
    *,
    miou_weight: float = 0.80,
    door_weight: float = 0.10,
    outlet_weight: float = 0.10,
) -> float:
    """Score a checkpoint while keeping global segmentation quality dominant."""
    weights = (miou_weight, door_weight, outlet_weight)
    if any(weight < 0 for weight in weights) or sum(weights) <= 0:
        raise ValueError("validation score weights must be non-negative and sum above zero")
    total = sum(weights)
    per_class = metrics["per_class"]
    miou = float(metrics["mean_iou"])
    door_iou = float(per_class["door"]["iou"] or 0.0)
    outlet_iou = float(per_class["outlet"]["iou"] or 0.0)
    return (
        miou_weight * miou
        + door_weight * door_iou
        + outlet_weight * outlet_iou
    ) / total


def save_checkpoint(
    path: Path,
    *,
    model: BakeSmartVenueUNet,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    validation_metrics: dict[str, object],
    balanced_score: float,
    config: dict[str, object],
    manifest_sha256: str,
    class_weights: list[float],
    profile: TrainingProfile = TrainingProfile(),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pt.part")
    torch.save(
        {
            "schema_version": profile.schema_version,
            "model_name": "BakeSmartVenueUNet",
            "training_variant": profile.training_variant,
            "num_classes": len(CLASS_NAMES),
            "class_names": list(CLASS_NAMES),
            "pretrained": False,
            "random_initialization": True,
            "v1_checkpoint_loaded": False,
            "v2_checkpoint_loaded": False,
            "training_data": profile.training_data,
            "validation_data": profile.validation_data,
            "test_data_used": False,
            "manifest_sha256": manifest_sha256,
            "epoch": epoch,
            "validation_metrics": validation_metrics,
            "balanced_validation_score": balanced_score,
            "class_weights": class_weights,
            "config": config,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        temporary,
    )
    temporary.replace(path)


def train(
    args: argparse.Namespace,
    *,
    profile: TrainingProfile = TrainingProfile(),
) -> dict[str, object]:
    set_seed(args.seed)
    device = choose_device(args.device)
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not manifest_path.is_file():
        raise ValueError("locked Step-3 split manifest is missing")

    manifest = load_locked_split_manifest(
        manifest_path,
        project_dir=PROJECT_DIR,
        expected_dataset=profile.expected_dataset,
    )
    train_samples = samples_for_split(
        manifest, "train", project_dir=PROJECT_DIR, verify_hashes=True
    )
    validation_samples = samples_for_split(
        manifest, "validation", project_dir=PROJECT_DIR, verify_hashes=True
    )
    # Deliberately no call requesting the locked test split.

    base_weights_cpu, pixel_counts = compute_train_class_weights(train_samples)
    balanced_weights_cpu = balanced_class_weights(
        base_weights_cpu,
        door_multiplier=args.door_weight_multiplier,
        outlet_multiplier=args.outlet_weight_multiplier,
        min_weight=args.minimum_class_weight,
        max_weight=args.maximum_class_weight,
    )
    class_weights = balanced_weights_cpu.to(device)

    train_dataset = RareClassTrainingDataset(
        train_samples,
        image_size=args.image_size,
        seed=args.seed,
        random_crops_per_scene=args.random_crops_per_scene,
        door_crops_per_scene=args.door_crops_per_scene,
        outlet_crops_per_scene=args.outlet_crops_per_scene,
    )
    validation_dataset = TiledValidationDataset(
        validation_samples,
        canvas_size=args.validation_canvas_size,
    )

    generator = torch.Generator()
    generator.manual_seed(args.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=1,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    model = BakeSmartVenueUNet(base_channels=args.base_channels).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    loss_fn = BalancedRareAwareLoss(class_weights).to(device)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=max(2, args.patience // 3),
        min_lr=1e-6,
    )

    view_summary = training_view_summary(train_dataset)
    config = {
        "seed": args.seed,
        "image_size": args.image_size,
        "validation_canvas_size": args.validation_canvas_size,
        "validation_tile_size": args.validation_tile_size,
        "validation_tile_stride": args.validation_tile_stride,
        "batch_size": args.batch_size,
        "epochs_requested": args.epochs,
        "patience": args.patience,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "grad_clip": args.grad_clip,
        "base_channels": args.base_channels,
        "random_crops_per_scene": args.random_crops_per_scene,
        "door_crops_per_scene": args.door_crops_per_scene,
        "outlet_crops_per_scene": args.outlet_crops_per_scene,
        "door_weight_multiplier": args.door_weight_multiplier,
        "outlet_weight_multiplier": args.outlet_weight_multiplier,
        "minimum_class_weight": args.minimum_class_weight,
        "maximum_class_weight": args.maximum_class_weight,
        "loss": "0.65 moderate weighted cross entropy + 0.35 weighted multiclass Dice",
        "checkpoint_selection": (
            "0.80 validation mIoU + 0.10 Door IoU + 0.10 Outlet IoU"
        ),
        "pretrained": False,
        "random_initialization": True,
        "v1_checkpoint_loaded": False,
        "v2_checkpoint_loaded": False,
        "test_split_loaded": False,
    }

    print(profile.title)
    print(f"Device:             {device}")
    print(f"Training scenes:    {len(train_samples)}")
    print(f"Validation scenes:  {len(validation_samples)}")
    print(f"Locked test used:   NO ({manifest['counts']['test']} remain untouched)")
    print(f"Training crop size: {args.image_size}x{args.image_size}")
    print(f"Validation canvas:  {args.validation_canvas_size}x{args.validation_canvas_size}")
    print(f"Parameters:         {count_parameters(model):,}")
    print("Initialization:     random (fresh model; no v1/v2/pretrained weights)")
    print("\nTraining views per epoch:")
    for key, value in view_summary.items():
        print(f"  {key:<14} {value}")
    print("\nRare-class scene presence:")
    print(f"  Door scenes:   {train_dataset.presence['door_scenes']}")
    print(f"  Outlet scenes: {train_dataset.presence['outlet_scenes']}")
    print("\nTrain-only class pixel counts / balanced weights:")
    for index, name in enumerate(CLASS_NAMES):
        print(
            f"  {name:<10} {pixel_counts[name]:>12,} px  "
            f"weight={float(balanced_weights_cpu[index]):.3f}"
        )
    print("\nCheckpoint score: 80% mIoU + 10% Door IoU + 10% Outlet IoU")
    print("Training...\n")

    manifest_sha = sha256_file(manifest_path)
    best_score = -math.inf
    best_epoch = 0
    best_metrics: dict[str, object] | None = None
    patience_left = args.patience
    history: list[dict[str, object]] = []
    best_path = output_dir / "best_model.pt"

    for epoch in range(1, args.epochs + 1):
        train_dataset.set_epoch(epoch)
        train_loss = run_train_epoch(
            model,
            train_loader,
            optimizer,
            loss_fn,
            device,
            grad_clip=args.grad_clip,
        )
        val_loss, metrics = run_validation(
            model,
            validation_loader,
            loss_fn,
            device,
            tile_size=args.validation_tile_size,
            tile_stride=args.validation_tile_stride,
        )
        score = balanced_validation_score(metrics)
        scheduler.step(score)
        lr = float(optimizer.param_groups[0]["lr"])
        improved = score > best_score + args.min_delta

        per_class = metrics["per_class"]
        door_iou = float(per_class["door"]["iou"] or 0.0)
        outlet_iou = float(per_class["outlet"]["iou"] or 0.0)
        miou = float(metrics["mean_iou"])

        if improved:
            best_score = score
            best_epoch = epoch
            best_metrics = metrics
            patience_left = args.patience
            save_checkpoint(
                best_path,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                validation_metrics=metrics,
                balanced_score=score,
                config=config,
                manifest_sha256=manifest_sha,
                class_weights=[float(value) for value in balanced_weights_cpu.tolist()],
                profile=profile,
            )
        else:
            patience_left -= 1

        history.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "validation_loss": round(val_loss, 6),
                "validation_mean_iou": metrics["mean_iou"],
                "validation_pixel_accuracy": metrics["pixel_accuracy"],
                "door_iou": round(door_iou, 6),
                "outlet_iou": round(outlet_iou, 6),
                "balanced_validation_score": round(score, 6),
                "learning_rate": lr,
                "best_so_far": improved,
            }
        )
        star = " *BEST*" if improved else ""
        print(
            f"Epoch {epoch:03d}/{args.epochs} | train {train_loss:.4f} | "
            f"val {val_loss:.4f} | mIoU {miou:.4f} | "
            f"door {door_iou:.4f} | outlet {outlet_iou:.4f} | "
            f"score {score:.4f} | acc {metrics['pixel_accuracy']:.4f} | "
            f"lr {lr:.2e}{star}",
            flush=True,
        )
        if patience_left <= 0:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    if best_metrics is None or not best_path.is_file():
        raise ValueError("v3 training finished without a valid best checkpoint")

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": profile.schema_version,
        "created_at_utc": utc_now(),
        "model_name": "BakeSmartVenueUNet",
        "training_variant": profile.training_variant,
        "training_data": profile.training_data,
        "validation_data": profile.validation_data,
        "checkpoint": str(best_path.relative_to(PROJECT_DIR)),
        "checkpoint_sha256": sha256_file(best_path),
        "split_manifest": str(manifest_path.relative_to(PROJECT_DIR)),
        "split_manifest_sha256": manifest_sha,
        "train_scene_count": len(train_samples),
        "validation_scene_count": len(validation_samples),
        "locked_test_scene_count": int(manifest["counts"]["test"]),
        "test_split_used": False,
        "pretrained": False,
        "random_initialization": True,
        "v1_checkpoint_loaded": False,
        "v2_checkpoint_loaded": False,
        "class_names": list(CLASS_NAMES),
        "train_class_pixel_counts": pixel_counts,
        "class_weights": {
            name: round(float(balanced_weights_cpu[index]), 6)
            for index, name in enumerate(CLASS_NAMES)
        },
        "training_view_summary": view_summary,
        "rare_class_scene_presence": train_dataset.presence,
        "best_epoch": best_epoch,
        "best_balanced_validation_score": round(best_score, 6),
        "best_validation_metrics": best_metrics,
        "config": config,
        "history": history,
        "production_ready": False,
        "next_step": profile.next_step,
    }
    report_path = output_dir / "validation_report.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(report_path)

    print(f"\n{profile.result_heading}")
    print(f"Epoch:          {best_epoch}")
    print(f"Balanced score: {best_score:.4f}")
    print(f"Mean IoU:       {best_metrics['mean_iou']:.4f}")
    print(f"Pixel accuracy: {best_metrics['pixel_accuracy']:.4f}")
    print("Per-class IoU:")
    for name in CLASS_NAMES:
        value = best_metrics["per_class"][name]["iou"]
        text = "n/a" if value is None else f"{float(value):.4f}"
        print(f"  {name:<10} {text}")
    print(f"\nCheckpoint: {best_path.relative_to(PROJECT_DIR)}")
    print(f"Report:     {report_path.relative_to(PROJECT_DIR)}")
    print(profile.prior_outputs_message)
    print("Locked test set remains untouched.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--validation-canvas-size", type=int, default=512)
    parser.add_argument("--validation-tile-size", type=int, default=256)
    parser.add_argument("--validation-tile-stride", type=int, default=192)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=70)
    parser.add_argument("--patience", type=int, default=14)
    parser.add_argument("--learning-rate", type=float, default=8e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--random-crops-per-scene", type=int, default=1)
    parser.add_argument("--door-crops-per-scene", type=int, default=2)
    parser.add_argument("--outlet-crops-per-scene", type=int, default=2)
    parser.add_argument("--door-weight-multiplier", type=float, default=1.20)
    parser.add_argument("--outlet-weight-multiplier", type=float, default=1.15)
    parser.add_argument("--minimum-class-weight", type=float, default=0.25)
    parser.add_argument("--maximum-class-weight", type=float, default=4.0)
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
