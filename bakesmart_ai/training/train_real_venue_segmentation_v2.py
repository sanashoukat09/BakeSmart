"""Train BakeSmart venue segmentation v2 with rare-class focused crops.

This keeps the Step-3 split unchanged, initializes a fresh six-class U-Net from
random weights, trains only on the 42 training scenes, validates only on the 9
validation scenes, and never loads the 9 locked test scenes.

Compared with v1, v2 adds Door/Outlet-focused crop oversampling, stronger rare
class loss weighting, and 512x512 tiled validation so tiny labels are not erased
by whole-room downscaling.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    import torch
    from torch.utils.data import DataLoader
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyTorch is required for Step 4 v2. Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR
from training.real_venue_segmentation import (
    BakeSmartVenueUNet,
    CLASS_NAMES,
    SegmentationConfusion,
    compute_train_class_weights,
    count_parameters,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
)
from training.real_venue_segmentation_v2 import (
    RareAwareSegmentationLoss,
    RareClassTrainingDataset,
    TiledValidationDataset,
    boosted_class_weights,
    tiled_logits,
    training_view_summary,
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
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_real_v2"
DEFAULT_SEED = 260824


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def choose_device(requested: str) -> torch.device:
    requested = requested.strip().lower()
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but PyTorch cannot access a CUDA GPU")
    if requested not in {"cpu", "cuda"}:
        raise ValueError("device must be auto, cpu, or cuda")
    return torch.device(requested)


def run_train_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn: RareAwareSegmentationLoss,
    device: torch.device,
    *,
    grad_clip: float,
) -> float:
    model.train()
    total = 0.0
    batches = 0
    for images, masks, _scene_ids in loader:
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = loss_fn(logits, masks)
        if not torch.isfinite(loss):
            raise ValueError("training loss became non-finite")
        loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        total += float(loss.detach().cpu())
        batches += 1
    return total / max(batches, 1)


@torch.no_grad()
def run_validation(
    model: torch.nn.Module,
    loader: DataLoader,
    loss_fn: RareAwareSegmentationLoss,
    device: torch.device,
    *,
    tile_size: int,
    tile_stride: int,
) -> tuple[float, dict[str, object]]:
    model.eval()
    confusion = SegmentationConfusion()
    total_loss = 0.0
    batches = 0
    for images, masks, _scene_ids in loader:
        # batch size is intentionally 1 for deterministic tiled validation.
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        logits = tiled_logits(
            model,
            images,
            tile_size=tile_size,
            stride=tile_stride,
        )
        loss = loss_fn(logits, masks)
        total_loss += float(loss.detach().cpu())
        batches += 1
        confusion.update(masks, torch.argmax(logits, dim=1))
    return total_loss / max(batches, 1), confusion.metrics()


def save_checkpoint(
    path: Path,
    *,
    model: BakeSmartVenueUNet,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    validation_metrics: dict[str, object],
    config: dict[str, object],
    manifest_sha256: str,
    class_weights: list[float],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pt.part")
    torch.save(
        {
            "schema_version": 2,
            "model_name": "BakeSmartVenueUNet",
            "training_variant": "rare_class_crops_v2",
            "num_classes": len(CLASS_NAMES),
            "class_names": list(CLASS_NAMES),
            "pretrained": False,
            "random_initialization": True,
            "training_data": "reviewed_real_v2_train_split_only",
            "validation_data": "reviewed_real_v2_validation_split_only",
            "test_data_used": False,
            "manifest_sha256": manifest_sha256,
            "epoch": epoch,
            "validation_metrics": validation_metrics,
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
        raise ValueError("locked Step-3 split manifest is missing")

    manifest = load_locked_split_manifest(manifest_path, project_dir=PROJECT_DIR)
    train_samples = samples_for_split(
        manifest, "train", project_dir=PROJECT_DIR, verify_hashes=True
    )
    validation_samples = samples_for_split(
        manifest, "validation", project_dir=PROJECT_DIR, verify_hashes=True
    )
    # Deliberately no request for the locked test split.

    base_weights_cpu, pixel_counts = compute_train_class_weights(train_samples)
    boosted_weights_cpu = boosted_class_weights(
        base_weights_cpu,
        door_multiplier=args.door_weight_multiplier,
        outlet_multiplier=args.outlet_weight_multiplier,
    )
    class_weights = boosted_weights_cpu.to(device)

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
    loss_fn = RareAwareSegmentationLoss(class_weights).to(device)
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
        "loss": "0.60 boosted weighted cross entropy + 0.40 weighted multiclass Dice",
        "checkpoint_selection": "highest validation mean IoU",
        "pretrained": False,
        "random_initialization": True,
        "test_split_loaded": False,
    }

    print("BakeSmart Step 4 v2 — Rare-Class Venue Segmentation")
    print(f"Device:             {device}")
    print(f"Training scenes:    {len(train_samples)}")
    print(f"Validation scenes:  {len(validation_samples)}")
    print(f"Locked test used:   NO ({manifest['counts']['test']} remain untouched)")
    print(f"Training crop size: {args.image_size}x{args.image_size}")
    print(f"Validation canvas:  {args.validation_canvas_size}x{args.validation_canvas_size}")
    print(f"Parameters:         {count_parameters(model):,}")
    print("Initialization:     random (fresh model, no v1 weights, no pretrained weights)")
    print("\nTraining views per epoch:")
    for key, value in view_summary.items():
        print(f"  {key:<14} {value}")
    print("\nRare-class scene presence:")
    print(f"  Door scenes:   {train_dataset.presence['door_scenes']}")
    print(f"  Outlet scenes: {train_dataset.presence['outlet_scenes']}")
    print("\nTrain-only class pixel counts / boosted weights:")
    for index, name in enumerate(CLASS_NAMES):
        print(
            f"  {name:<10} {pixel_counts[name]:>12,} px  "
            f"weight={float(boosted_weights_cpu[index]):.3f}"
        )
    print("\nTraining...\n")

    manifest_sha = sha256_file(manifest_path)
    best_miou = -math.inf
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
        miou = float(metrics["mean_iou"])
        scheduler.step(miou)
        lr = float(optimizer.param_groups[0]["lr"])
        improved = miou > best_miou + args.min_delta
        if improved:
            best_miou = miou
            best_epoch = epoch
            best_metrics = metrics
            patience_left = args.patience
            save_checkpoint(
                best_path,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                validation_metrics=metrics,
                config=config,
                manifest_sha256=manifest_sha,
                class_weights=[float(v) for v in boosted_weights_cpu.tolist()],
            )
        else:
            patience_left -= 1

        per_class = metrics["per_class"]
        door_iou = per_class["door"]["iou"] or 0.0
        outlet_iou = per_class["outlet"]["iou"] or 0.0
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "validation_loss": round(val_loss, 6),
                "validation_mean_iou": metrics["mean_iou"],
                "validation_pixel_accuracy": metrics["pixel_accuracy"],
                "door_iou": door_iou,
                "outlet_iou": outlet_iou,
                "learning_rate": lr,
                "best_so_far": improved,
            }
        )
        star = " *BEST*" if improved else ""
        print(
            f"Epoch {epoch:03d}/{args.epochs} | train {train_loss:.4f} | "
            f"val {val_loss:.4f} | mIoU {miou:.4f} | "
            f"door {float(door_iou):.4f} | outlet {float(outlet_iou):.4f} | "
            f"acc {metrics['pixel_accuracy']:.4f} | lr {lr:.2e}{star}",
            flush=True,
        )
        if patience_left <= 0:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    if best_metrics is None or not best_path.is_file():
        raise ValueError("v2 training finished without a valid best checkpoint")

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 2,
        "created_at_utc": utc_now(),
        "model_name": "BakeSmartVenueUNet",
        "training_variant": "rare_class_crops_v2",
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
        "class_names": list(CLASS_NAMES),
        "train_class_pixel_counts": pixel_counts,
        "class_weights": {
            name: round(float(boosted_weights_cpu[index]), 6)
            for index, name in enumerate(CLASS_NAMES)
        },
        "training_view_summary": view_summary,
        "rare_class_scene_presence": train_dataset.presence,
        "best_epoch": best_epoch,
        "best_validation_metrics": best_metrics,
        "config": config,
        "history": history,
        "production_ready": False,
        "next_step": "compare v2 validation result with v1 before locked-test evaluation",
    }
    report_path = output_dir / "validation_report.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)

    print("\nBest v2 validation result")
    print(f"Epoch:          {best_epoch}")
    print(f"Mean IoU:       {best_metrics['mean_iou']:.4f}")
    print(f"Pixel accuracy: {best_metrics['pixel_accuracy']:.4f}")
    print("Per-class IoU:")
    for name in CLASS_NAMES:
        value = best_metrics["per_class"][name]["iou"]
        text = "n/a" if value is None else f"{float(value):.4f}"
        print(f"  {name:<10} {text}")
    print(f"\nCheckpoint: {best_path.relative_to(PROJECT_DIR)}")
    print(f"Report:     {report_path.relative_to(PROJECT_DIR)}")
    print("v1 checkpoint remains untouched.")
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
    parser.add_argument("--outlet-crops-per-scene", type=int, default=5)
    parser.add_argument("--door-weight-multiplier", type=float, default=1.8)
    parser.add_argument("--outlet-weight-multiplier", type=float, default=3.5)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser


def main() -> int:
    if "BAKESMART_TORCH_THREADS" in os.environ:
        torch.set_num_threads(max(1, int(os.environ["BAKESMART_TORCH_THREADS"])))
    try:
        train(build_parser().parse_args())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
