"""Train BakeSmart v5 with transfer learning and corrected rare-aware labels.

v5 uses a pretrained LR-ASPP MobileNetV3 model, ImageNet normalization,
higher-resolution crops, head-only warmup, and rare-class-focused sampling. It
loads only the rebalanced corrected train/validation split and never requests
the locked test split.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision.models.segmentation import (
        LRASPP_MobileNet_V3_Large_Weights,
        lraspp_mobilenet_v3_large,
    )
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyTorch and torchvision are required for v5. Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR
from training.real_venue_segmentation import (
    CLASS_NAMES,
    NUM_CLASSES,
    compute_train_class_weights,
    count_parameters,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
)
from training.real_venue_segmentation_v2 import (
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
from training.train_real_venue_segmentation_v3 import (
    BalancedRareAwareLoss,
    balanced_class_weights,
    balanced_validation_score,
)


DEFAULT_MANIFEST = (
    PROJECT_DIR / "data" / "venue_vision" / "raw" / "real_v2_repaired"
    / "splits" / "v5_split_manifest.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_real_v5"
DEFAULT_SEED = 260828


class BakeSmartLRASPP(nn.Module):
    """Six-class LR-ASPP with a pretrained MobileNetV3 feature extractor."""

    def __init__(self) -> None:
        super().__init__()
        weights = LRASPP_MobileNet_V3_Large_Weights.DEFAULT
        self.network = lraspp_mobilenet_v3_large(weights=weights)
        low = self.network.classifier.low_classifier
        high = self.network.classifier.high_classifier
        self.network.classifier.low_classifier = nn.Conv2d(
            low.in_channels, NUM_CLASSES, kernel_size=1
        )
        self.network.classifier.high_classifier = nn.Conv2d(
            high.in_channels, NUM_CLASSES, kernel_size=1
        )
        nn.init.kaiming_normal_(
            self.network.classifier.low_classifier.weight, mode="fan_out", nonlinearity="relu"
        )
        nn.init.kaiming_normal_(
            self.network.classifier.high_classifier.weight, mode="fan_out", nonlinearity="relu"
        )
        nn.init.zeros_(self.network.classifier.low_classifier.bias)
        nn.init.zeros_(self.network.classifier.high_classifier.bias)

    @property
    def backbone(self) -> nn.Module:
        return self.network.backbone

    @property
    def classifier(self) -> nn.Module:
        return self.network.classifier

    def freeze_backbone(self, frozen: bool) -> None:
        for parameter in self.backbone.parameters():
            parameter.requires_grad = not frozen

    def train(self, mode: bool = True) -> "BakeSmartLRASPP":
        super().train(mode)
        if mode:
            # Batch size is tiny; preserve pretrained running statistics.
            for module in self.modules():
                if isinstance(module, nn.BatchNorm2d):
                    module.eval()
        return self

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.network(inputs)["out"]


def _validate_v5_manifest(manifest: dict[str, object]) -> None:
    required = {
        "development_membership_rebalanced": True,
        "test_membership_preserved": True,
        "test_rows_reused_verbatim": True,
        "test_split_used": False,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise ValueError(f"v5 manifest requires {key}={expected!r}")
    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("v5 manifest has no class-presence summary")
    presence = summary.get("class_presence_by_split")
    if not isinstance(presence, dict) or not isinstance(presence.get("validation"), dict):
        raise ValueError("v5 manifest has no validation class-presence summary")
    if int(presence["validation"].get("2", 0)) < 2:
        raise ValueError("v5 validation requires at least two Door scenes")
    if int(presence["validation"].get("5", 0)) < 1:
        raise ValueError("v5 validation requires at least one Outlet scene")


def _save_checkpoint(
    path: Path,
    *,
    model: BakeSmartLRASPP,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    metrics: dict[str, object],
    score: float,
    manifest_sha: str,
    class_weights: list[float],
    config: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pt.part")
    torch.save(
        {
            "schema_version": 5,
            "model_name": "BakeSmartLRASPP",
            "architecture": "lraspp_mobilenet_v3_large",
            "training_variant": "pretrained_high_resolution_rare_aware_v5",
            "num_classes": NUM_CLASSES,
            "class_names": list(CLASS_NAMES),
            "pretrained": True,
            "pretrained_weights": "LRASPP_MobileNet_V3_Large_Weights.DEFAULT",
            "random_initialization": False,
            "training_data": "corrected_v5_train_split_only",
            "validation_data": "corrected_v5_validation_split_only",
            "test_data_used": False,
            "manifest_sha256": manifest_sha,
            "epoch": epoch,
            "validation_metrics": metrics,
            "balanced_validation_score": score,
            "class_weights": class_weights,
            "config": config,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        temporary,
    )
    temporary.replace(path)


def train(args: argparse.Namespace) -> dict[str, object]:
    set_seed(args.seed)
    device = choose_device(args.device)
    manifest_path = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not manifest_path.is_file():
        raise ValueError(
            "v5 split manifest is missing; run python -m training.prepare_real_venue_v5_split"
        )
    manifest = load_locked_split_manifest(
        manifest_path,
        project_dir=PROJECT_DIR,
        expected_dataset="real_v2_repaired",
    )
    _validate_v5_manifest(manifest)
    train_samples = samples_for_split(
        manifest, "train", project_dir=PROJECT_DIR, verify_hashes=True
    )
    validation_samples = samples_for_split(
        manifest, "validation", project_dir=PROJECT_DIR, verify_hashes=True
    )
    # Deliberately no request for the locked test split.

    base_weights, pixel_counts = compute_train_class_weights(train_samples)
    balanced_weights = balanced_class_weights(
        base_weights,
        door_multiplier=args.door_weight_multiplier,
        outlet_multiplier=args.outlet_weight_multiplier,
        min_weight=args.minimum_class_weight,
        max_weight=args.maximum_class_weight,
    )
    train_dataset = RareClassTrainingDataset(
        train_samples,
        image_size=args.image_size,
        seed=args.seed,
        random_crops_per_scene=args.random_crops_per_scene,
        door_crops_per_scene=args.door_crops_per_scene,
        outlet_crops_per_scene=args.outlet_crops_per_scene,
        normalization="imagenet",
    )
    validation_dataset = TiledValidationDataset(
        validation_samples,
        canvas_size=args.validation_canvas_size,
        normalization="imagenet",
    )
    generator = torch.Generator().manual_seed(args.seed)
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

    print("Loading free pretrained MobileNetV3/LR-ASPP weights...")
    model = BakeSmartLRASPP().to(device)
    model.freeze_backbone(True)
    optimizer = torch.optim.AdamW(
        [
            {"params": model.backbone.parameters(), "lr": args.backbone_learning_rate},
            {"params": model.classifier.parameters(), "lr": args.learning_rate},
        ],
        weight_decay=args.weight_decay,
    )
    loss_fn = BalancedRareAwareLoss(balanced_weights.to(device)).to(device)
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
        "head_warmup_epochs": args.head_warmup_epochs,
        "learning_rate": args.learning_rate,
        "backbone_learning_rate": args.backbone_learning_rate,
        "weight_decay": args.weight_decay,
        "grad_clip": args.grad_clip,
        "random_crops_per_scene": args.random_crops_per_scene,
        "door_crops_per_scene": args.door_crops_per_scene,
        "outlet_crops_per_scene": args.outlet_crops_per_scene,
        "door_weight_multiplier": args.door_weight_multiplier,
        "outlet_weight_multiplier": args.outlet_weight_multiplier,
        "minimum_class_weight": args.minimum_class_weight,
        "maximum_class_weight": args.maximum_class_weight,
        "normalization": "imagenet",
        "batch_norm_running_statistics": "frozen",
        "loss": "0.65 weighted cross entropy + 0.35 weighted multiclass Dice",
        "checkpoint_selection": "0.80 validation mIoU + 0.10 Door IoU + 0.10 Outlet IoU",
        "test_split_loaded": False,
    }

    print("BakeSmart Step 4 v5 — Pretrained High-Resolution Venue Segmentation")
    print(f"Device:             {device}")
    print(f"Training scenes:    {len(train_samples)}")
    print(f"Validation scenes:  {len(validation_samples)}")
    print(f"Locked test used:   NO ({manifest['counts']['test']} remain untouched)")
    print(f"Training crop size: {args.image_size}x{args.image_size}")
    print(f"Validation canvas:  {args.validation_canvas_size}x{args.validation_canvas_size}")
    print(f"Parameters:         {count_parameters(model):,}")
    print(f"Head warmup:        {args.head_warmup_epochs} epoch(s)")
    print("Initialization:     pretrained LR-ASPP/MobileNetV3; new six-class heads")
    print("\nTraining views per epoch:")
    for key, value in view_summary.items():
        print(f"  {key:<14} {value}")
    print("\nRare-class scene presence:")
    print(f"  Door scenes:   {train_dataset.presence['door_scenes']}")
    print(f"  Outlet scenes: {train_dataset.presence['outlet_scenes']}")
    print("\nTrain-only class pixel counts / weights:")
    for index, name in enumerate(CLASS_NAMES):
        print(
            f"  {name:<10} {pixel_counts[name]:>12,} px  "
            f"weight={float(balanced_weights[index]):.3f}"
        )
    print("\nTraining...\n")

    manifest_sha = sha256_file(manifest_path)
    best_score = -math.inf
    best_epoch = 0
    best_metrics: dict[str, object] | None = None
    patience_left = args.patience
    history: list[dict[str, object]] = []
    best_path = output_dir / "best_model.pt"

    for epoch in range(1, args.epochs + 1):
        if epoch == args.head_warmup_epochs + 1:
            model.freeze_backbone(False)
            print("Backbone unfrozen for fine-tuning.", flush=True)
        train_dataset.set_epoch(epoch)
        train_loss = run_train_epoch(
            model, train_loader, optimizer, loss_fn, device, grad_clip=args.grad_clip
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
        improved = score > best_score + args.min_delta
        if improved:
            best_score = score
            best_epoch = epoch
            best_metrics = metrics
            patience_left = args.patience
            _save_checkpoint(
                best_path,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                metrics=metrics,
                score=score,
                manifest_sha=manifest_sha,
                class_weights=[float(value) for value in balanced_weights.tolist()],
                config=config,
            )
        else:
            patience_left -= 1

        per_class = metrics["per_class"]
        door_iou = float(per_class["door"]["iou"] or 0.0)
        outlet_iou = float(per_class["outlet"]["iou"] or 0.0)
        miou = float(metrics["mean_iou"])
        lr = float(optimizer.param_groups[1]["lr"])
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
                "head_learning_rate": lr,
                "best_so_far": improved,
            }
        )
        star = " *BEST*" if improved else ""
        print(
            f"Epoch {epoch:03d}/{args.epochs} | train {train_loss:.4f} | "
            f"val {val_loss:.4f} | mIoU {miou:.4f} | door {door_iou:.4f} | "
            f"outlet {outlet_iou:.4f} | score {score:.4f} | "
            f"acc {metrics['pixel_accuracy']:.4f} | lr {lr:.2e}{star}",
            flush=True,
        )
        if patience_left <= 0:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    if best_metrics is None or not best_path.is_file():
        raise ValueError("v5 training finished without a valid checkpoint")
    report = {
        "schema_version": 5,
        "created_at_utc": utc_now(),
        "model_name": "BakeSmartLRASPP",
        "architecture": "lraspp_mobilenet_v3_large",
        "training_variant": "pretrained_high_resolution_rare_aware_v5",
        "checkpoint": str(best_path.relative_to(PROJECT_DIR)),
        "checkpoint_sha256": sha256_file(best_path),
        "split_manifest": str(manifest_path.relative_to(PROJECT_DIR)),
        "split_manifest_sha256": manifest_sha,
        "train_scene_count": len(train_samples),
        "validation_scene_count": len(validation_samples),
        "locked_test_scene_count": int(manifest["counts"]["test"]),
        "test_split_used": False,
        "pretrained": True,
        "pretrained_weights": "LRASPP_MobileNet_V3_Large_Weights.DEFAULT",
        "class_names": list(CLASS_NAMES),
        "train_class_pixel_counts": pixel_counts,
        "class_weights": {
            name: round(float(balanced_weights[index]), 6)
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
        "next_step": "review v5 validation predictions before one locked-test evaluation",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_report.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)

    print("\nBest v5 validation result")
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
    print("All previous model outputs remain untouched.")
    print("Locked test set remains untouched.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--image-size", type=int, default=320)
    parser.add_argument("--validation-canvas-size", type=int, default=640)
    parser.add_argument("--validation-tile-size", type=int, default=320)
    parser.add_argument("--validation-tile-stride", type=int, default=240)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--head-warmup-epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=4e-4)
    parser.add_argument("--backbone-learning-rate", type=float, default=8e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--random-crops-per-scene", type=int, default=1)
    parser.add_argument("--door-crops-per-scene", type=int, default=3)
    parser.add_argument("--outlet-crops-per-scene", type=int, default=6)
    parser.add_argument("--door-weight-multiplier", type=float, default=1.4)
    parser.add_argument("--outlet-weight-multiplier", type=float, default=1.6)
    parser.add_argument("--minimum-class-weight", type=float, default=0.25)
    parser.add_argument("--maximum-class-weight", type=float, default=6.0)
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
