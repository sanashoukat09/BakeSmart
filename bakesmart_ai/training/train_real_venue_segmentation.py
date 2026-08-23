"""Train BakeSmart's real six-class venue segmentation model from scratch.

This Step-4 trainer reads the locked Step-3 manifest, loads only the train and
validation splits, initializes BakeSmartVenueUNet from random weights, trains
with weighted cross-entropy + Dice loss, selects the best checkpoint by
validation mean IoU, and writes validation-only metrics.

The locked test split is deliberately never loaded here.

Run from ``bakesmart_ai``::

    python -m training.train_real_venue_segmentation
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
        "PyTorch is required for Step 4. Run: pip install -r requirements.txt"
    ) from exc

from training.annotation_workspace import PROJECT_DIR
from training.real_venue_segmentation import (
    BakeSmartVenueUNet,
    CLASS_NAMES,
    CombinedSegmentationLoss,
    RealVenueSegmentationDataset,
    SegmentationConfusion,
    compute_train_class_weights,
    count_parameters,
    load_locked_split_manifest,
    samples_for_split,
    sha256_file,
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
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "models" / "venue_vision_real_v1"
DEFAULT_SEED = 260823


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
    loss_fn: CombinedSegmentationLoss,
    device: torch.device,
    *,
    grad_clip: float,
) -> float:
    model.train()
    total_loss = 0.0
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
        total_loss += float(loss.detach().cpu())
        batches += 1
    return total_loss / max(batches, 1)


@torch.no_grad()
def run_validation(
    model: torch.nn.Module,
    loader: DataLoader,
    loss_fn: CombinedSegmentationLoss,
    device: torch.device,
) -> tuple[float, dict[str, object]]:
    model.eval()
    total_loss = 0.0
    batches = 0
    confusion = SegmentationConfusion()
    for images, masks, _scene_ids in loader:
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        logits = model(images)
        loss = loss_fn(logits, masks)
        total_loss += float(loss.detach().cpu())
        batches += 1
        predictions = torch.argmax(logits, dim=1)
        confusion.update(masks, predictions)
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
            "schema_version": 1,
            "model_name": "BakeSmartVenueUNet",
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
        raise ValueError(
            "locked split manifest not found. Complete Step 3 first: "
            f"{manifest_path}"
        )

    manifest = load_locked_split_manifest(manifest_path, project_dir=PROJECT_DIR)
    train_samples = samples_for_split(
        manifest,
        "train",
        project_dir=PROJECT_DIR,
        verify_hashes=True,
    )
    validation_samples = samples_for_split(
        manifest,
        "validation",
        project_dir=PROJECT_DIR,
        verify_hashes=True,
    )
    # Intentionally no call to samples_for_split(..., "test").

    if len(train_samples) != int(manifest["counts"]["train"]):
        raise ValueError("training sample count does not match locked manifest")
    if len(validation_samples) != int(manifest["counts"]["validation"]):
        raise ValueError("validation sample count does not match locked manifest")

    class_weights_cpu, class_pixel_counts = compute_train_class_weights(train_samples)
    class_weights = class_weights_cpu.to(device)

    train_dataset = RealVenueSegmentationDataset(
        train_samples,
        image_size=args.image_size,
        augment=True,
        seed=args.seed,
    )
    validation_dataset = RealVenueSegmentationDataset(
        validation_samples,
        image_size=args.image_size,
        augment=False,
        seed=args.seed,
    )
    data_generator = torch.Generator()
    data_generator.manual_seed(args.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
        generator=data_generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
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
    loss_fn = CombinedSegmentationLoss(class_weights).to(device)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=max(2, args.patience // 3),
        min_lr=1e-6,
    )

    manifest_sha = sha256_file(manifest_path)
    config = {
        "seed": args.seed,
        "image_size": args.image_size,
        "batch_size": args.batch_size,
        "epochs_requested": args.epochs,
        "patience": args.patience,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "grad_clip": args.grad_clip,
        "base_channels": args.base_channels,
        "device": str(device),
        "augmentation": {
            "horizontal_flip_probability": 0.5,
            "brightness_range": [0.85, 1.15],
            "contrast_range": [0.90, 1.10],
        },
        "loss": "0.70 weighted cross entropy + 0.30 multiclass Dice",
        "checkpoint_selection": "highest validation mean IoU",
        "pretrained": False,
        "random_initialization": True,
        "test_split_loaded": False,
    }

    print("BakeSmart Step 4 — Real Venue Segmentation Training")
    print(f"Device:           {device}")
    print(f"Training scenes:  {len(train_samples)}")
    print(f"Validation scenes:{len(validation_samples)}")
    print(f"Locked test used: NO ({manifest['counts']['test']} scenes remain untouched)")
    print(f"Image size:       {args.image_size}x{args.image_size}")
    print(f"Parameters:       {count_parameters(model):,}")
    print("Initialization:   random (no pretrained weights)")
    print("\nTrain-only class pixel counts:")
    for name in CLASS_NAMES:
        print(f"  {name:<10} {class_pixel_counts[name]:>12,}")
    print("\nTraining...\n")

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
        validation_loss, validation_metrics = run_validation(
            model,
            validation_loader,
            loss_fn,
            device,
        )
        miou = float(validation_metrics["mean_iou"])
        scheduler.step(miou)
        current_lr = float(optimizer.param_groups[0]["lr"])
        improved = miou > best_miou + args.min_delta
        if improved:
            best_miou = miou
            best_epoch = epoch
            best_metrics = validation_metrics
            patience_left = args.patience
            save_checkpoint(
                best_path,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                validation_metrics=validation_metrics,
                config=config,
                manifest_sha256=manifest_sha,
                class_weights=[float(value) for value in class_weights_cpu.tolist()],
            )
        else:
            patience_left -= 1

        history.append(
            {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "validation_loss": round(validation_loss, 6),
                "validation_mean_iou": validation_metrics["mean_iou"],
                "validation_pixel_accuracy": validation_metrics["pixel_accuracy"],
                "learning_rate": current_lr,
                "best_so_far": improved,
            }
        )
        star = " *BEST*" if improved else ""
        print(
            f"Epoch {epoch:03d}/{args.epochs} | "
            f"train loss {train_loss:.4f} | val loss {validation_loss:.4f} | "
            f"val mIoU {miou:.4f} | pixel acc {validation_metrics['pixel_accuracy']:.4f} | "
            f"lr {current_lr:.2e}{star}",
            flush=True,
        )
        if patience_left <= 0:
            print(f"Early stopping after epoch {epoch}; best epoch was {best_epoch}.")
            break

    if best_metrics is None or not best_path.is_file():
        raise ValueError("training finished without a valid best checkpoint")

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "model_name": "BakeSmartVenueUNet",
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
        "class_names": list(CLASS_NAMES),
        "train_class_pixel_counts": class_pixel_counts,
        "class_weights": {
            name: round(float(class_weights_cpu[index]), 6)
            for index, name in enumerate(CLASS_NAMES)
        },
        "best_epoch": best_epoch,
        "best_validation_metrics": best_metrics,
        "config": config,
        "history": history,
        "production_ready": False,
        "next_step": "final locked-test evaluation after model development is frozen",
    }
    report_path = output_dir / "validation_report.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)

    print("\nBest validation result")
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
    print("Locked test set remains untouched.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--min-delta", type=float, default=1e-4)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser


def main() -> int:
    # Keeps CPU thread use reasonable on laptops while allowing override.
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
