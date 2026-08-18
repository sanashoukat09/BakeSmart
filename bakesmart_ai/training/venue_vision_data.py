"""Deterministic synthetic venue scenes and leakage-safe pixel matrices.

The generated scenes are a bootstrap dataset, not a substitute for labelled
customer venue photographs. Real images must use the adjacent annotation schema
and must never be mixed across train/validation/test by scene ID.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from training.model_data import ModelSplit


VENUE_LABELS = (
    "wall",
    "floor",
    "door",
    "window",
    "furniture",
    "outlet",
    "walkway",
)
LABEL_TO_ID = {label: index for index, label in enumerate(VENUE_LABELS)}
DEFAULT_VENUE_DATA_DIR = (
    Path(__file__).resolve().parents[1] / "data" / "venue_vision" / "v1"
)
INDEX_COLUMNS = (
    "scene_id",
    "split",
    "seed",
    "label_source",
    "review_status",
    "production_approved",
)
REAL_ANNOTATION_COLUMNS = (
    "scene_id",
    "image_path",
    "mask_path",
    "split",
    "source_url",
    "license",
    "consent_or_rights_confirmed",
    "annotator_id",
    "reviewer_id",
    "review_status",
    "notes",
)


@dataclass(frozen=True)
class VenueSceneRecord:
    scene_id: str
    split: str
    seed: int


def build_index_records(
    *,
    scene_count: int = 240,
    seed: int = 20260818,
) -> list[VenueSceneRecord]:
    if scene_count < 30:
        raise ValueError("venue bootstrap requires at least 30 scenes")
    rng = np.random.default_rng(seed)
    scene_seeds = rng.choice(
        np.arange(1, 10_000_000, dtype=np.int64),
        size=scene_count,
        replace=False,
    )
    train_end = round(scene_count * 0.70)
    validation_end = train_end + round(scene_count * 0.15)
    records: list[VenueSceneRecord] = []
    for index, scene_seed in enumerate(scene_seeds):
        if index < train_end:
            split = "train"
        elif index < validation_end:
            split = "validation"
        else:
            split = "test"
        records.append(
            VenueSceneRecord(
                scene_id=f"venue-synthetic-{index + 1:04d}",
                split=split,
                seed=int(scene_seed),
            )
        )
    return records


def write_dataset_contract(
    output_dir: Path = DEFAULT_VENUE_DATA_DIR,
    *,
    scene_count: int = 240,
    seed: int = 20260818,
) -> list[VenueSceneRecord]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = build_index_records(scene_count=scene_count, seed=seed)
    with (output_dir / "synthetic_index.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "scene_id": record.scene_id,
                    "split": record.split,
                    "seed": record.seed,
                    "label_source": "deterministic_synthetic_geometry_v1",
                    "review_status": "synthetic_bootstrap_only",
                    "production_approved": "false",
                }
            )
    real_template = output_dir / "real_annotations_template.csv"
    if not real_template.exists():
        with real_template.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(
                handle,
                fieldnames=REAL_ANNOTATION_COLUMNS,
                lineterminator="\n",
            ).writeheader()
    report = validate_dataset_contract(output_dir)
    (output_dir / "dataset_report.json").write_text(
        f"{json.dumps(report, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return records


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_dataset_contract(
    data_dir: Path = DEFAULT_VENUE_DATA_DIR,
) -> dict[str, object]:
    records = load_index(data_dir)
    counts = {
        split: sum(record.split == split for record in records)
        for split in ("train", "validation", "test")
    }
    real_path = data_dir / "real_annotations_template.csv"
    with real_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REAL_ANNOTATION_COLUMNS:
            raise ValueError("real venue annotation schema is invalid")
        real_rows = list(reader)
    approved_real_rows = 0
    seen_real_scenes: set[str] = set()
    allowed_root = data_dir.parent.resolve()
    for row_number, row in enumerate(real_rows, start=2):
        missing = [column for column in REAL_ANNOTATION_COLUMNS if not row[column]]
        if missing:
            raise ValueError(
                f"real annotation row {row_number} has blank fields: {missing}"
            )
        if row["split"] not in {"train", "validation", "test"}:
            raise ValueError(f"real annotation row {row_number} has invalid split")
        if row["scene_id"] in seen_real_scenes:
            raise ValueError("real annotation scene IDs must be unique")
        seen_real_scenes.add(row["scene_id"])
        if row["consent_or_rights_confirmed"].lower() != "true":
            raise ValueError(
                f"real annotation row {row_number} lacks confirmed rights or consent"
            )
        if row["review_status"] == "approved":
            approved_real_rows += 1
        image_path = (data_dir / row["image_path"]).resolve()
        mask_path = (data_dir / row["mask_path"]).resolve()
        if (
            allowed_root not in image_path.parents
            or allowed_root not in mask_path.parents
        ):
            raise ValueError(
                "real venue image and mask paths must stay in venue_vision"
            )
        if not image_path.is_file() or not mask_path.is_file():
            raise ValueError(f"real annotation row {row_number} files are missing")
        with Image.open(image_path) as image, Image.open(mask_path) as mask_image:
            if image.size != mask_image.size:
                raise ValueError(
                    f"real annotation row {row_number} image and mask sizes differ"
                )
            mask = np.asarray(mask_image)
        if mask.ndim != 2:
            raise ValueError(
                f"real annotation row {row_number} mask must be single-channel"
            )
        invalid_labels = set(int(value) for value in np.unique(mask)) - set(
            range(len(VENUE_LABELS))
        )
        if invalid_labels:
            raise ValueError(
                f"real annotation row {row_number} has invalid mask IDs {invalid_labels}"
            )
    return {
        "dataset_version": "venue-vision-v1",
        "synthetic_scene_counts": counts,
        "synthetic_scene_total": len(records),
        "real_annotation_rows": len(real_rows),
        "approved_real_annotation_rows": approved_real_rows,
        "labels": list(VENUE_LABELS),
        "artifacts": {
            "synthetic_index_sha256": _sha256(data_dir / "synthetic_index.csv"),
            "real_annotations_template_sha256": _sha256(real_path),
        },
        "training_gate": {
            "synthetic_bootstrap_ready": True,
            "real_photo_training_ready": approved_real_rows >= 100,
            "real_photo_production_evaluation_ready": False,
        },
    }


def load_index(
    data_dir: Path = DEFAULT_VENUE_DATA_DIR,
) -> list[VenueSceneRecord]:
    path = data_dir / "synthetic_index.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != INDEX_COLUMNS:
            raise ValueError("venue synthetic index schema is invalid")
        rows = list(reader)
    records = [
        VenueSceneRecord(
            scene_id=row["scene_id"],
            split=row["split"],
            seed=int(row["seed"]),
        )
        for row in rows
    ]
    if not records:
        raise ValueError("venue synthetic index is empty")
    if len({record.scene_id for record in records}) != len(records):
        raise ValueError("venue synthetic index contains duplicate scene IDs")
    if {record.split for record in records} != {"train", "validation", "test"}:
        raise ValueError("venue synthetic index must contain all locked splits")
    return records


def render_synthetic_scene(
    seed: int,
    *,
    size: int = 48,
) -> tuple[np.ndarray, np.ndarray]:
    """Return one RGB elevation image and its exact seven-class mask."""

    if size < 32:
        raise ValueError("synthetic venue scenes require size >= 32")
    rng = np.random.default_rng(seed)
    boundary = int(rng.integers(round(size * 0.55), round(size * 0.72)))
    wall_colour = rng.integers(175, 241, size=3)
    floor_colour = rng.integers(75, 156, size=3)
    image = np.empty((size, size, 3), dtype=np.float64)
    image[:boundary] = wall_colour
    image[boundary:] = floor_colour
    mask = np.full((size, size), LABEL_TO_ID["wall"], dtype=np.int64)
    mask[boundary:] = LABEL_TO_ID["floor"]

    horizontal_light = np.linspace(
        rng.uniform(-18, 3), rng.uniform(3, 20), size, dtype=np.float64
    )[None, :, None]
    image += horizontal_light
    image += rng.normal(0, 5.5, size=image.shape)

    walkway_half = int(rng.integers(max(3, size // 10), max(4, size // 6)))
    walkway_center = int(rng.integers(size // 3, 2 * size // 3))
    walkway_left = max(0, walkway_center - walkway_half)
    walkway_right = min(size, walkway_center + walkway_half)
    image[boundary:, walkway_left:walkway_right] = np.clip(
        image[boundary:, walkway_left:walkway_right] + rng.uniform(22, 45),
        0,
        255,
    )
    mask[boundary:, walkway_left:walkway_right] = LABEL_TO_ID["walkway"]

    door_width = int(rng.integers(max(4, size // 9), max(6, size // 6)))
    door_left = int(rng.integers(1, size - door_width - 1))
    door_top = int(rng.integers(max(2, boundary // 7), max(3, boundary // 3)))
    image[door_top:boundary, door_left : door_left + door_width] = rng.integers(
        70, 171, size=3
    )
    mask[door_top:boundary, door_left : door_left + door_width] = LABEL_TO_ID["door"]

    window_width = int(rng.integers(max(5, size // 8), max(7, size // 4)))
    window_height = int(rng.integers(max(4, size // 9), max(6, size // 5)))
    window_left = int(rng.integers(1, size - window_width - 1))
    window_top = int(rng.integers(2, max(3, boundary - window_height - 2)))
    image[
        window_top : window_top + window_height,
        window_left : window_left + window_width,
    ] = np.asarray(
        [rng.integers(95, 155), rng.integers(145, 205), rng.integers(175, 235)]
    )
    mask[
        window_top : window_top + window_height,
        window_left : window_left + window_width,
    ] = LABEL_TO_ID["window"]

    furniture_width = int(rng.integers(max(7, size // 6), max(9, size // 3)))
    furniture_height = int(rng.integers(max(4, size // 10), max(6, size // 5)))
    furniture_left = int(rng.integers(0, size - furniture_width))
    furniture_top = max(0, boundary - furniture_height)
    image[
        furniture_top:boundary,
        furniture_left : furniture_left + furniture_width,
    ] = rng.integers(45, 155, size=3)
    mask[
        furniture_top:boundary,
        furniture_left : furniture_left + furniture_width,
    ] = LABEL_TO_ID["furniture"]

    outlet_size = max(2, size // 24)
    outlet_left = int(rng.integers(1, size - outlet_size - 1))
    outlet_top = int(rng.integers(max(2, boundary // 2), boundary - outlet_size))
    image[
        outlet_top : outlet_top + outlet_size,
        outlet_left : outlet_left + outlet_size,
    ] = rng.integers(25, 80, size=3)
    mask[
        outlet_top : outlet_top + outlet_size,
        outlet_left : outlet_left + outlet_size,
    ] = LABEL_TO_ID["outlet"]

    return np.clip(image, 0, 255).astype(np.uint8), mask


def extract_pixel_features(image: np.ndarray) -> np.ndarray:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("venue image must have shape H x W x 3")
    height, width, _ = image.shape
    normalized = image.astype(np.float64) / 127.5 - 1.0
    padded = np.pad(normalized, ((1, 1), (1, 1), (0, 0)), mode="reflect")
    neighbours = [
        padded[y : y + height, x : x + width] for y in range(3) for x in range(3)
    ]
    row_coordinates = np.linspace(-1.0, 1.0, height)[:, None]
    column_coordinates = np.linspace(-1.0, 1.0, width)[None, :]
    rows = np.broadcast_to(row_coordinates, (height, width))[..., None]
    columns = np.broadcast_to(column_coordinates, (height, width))[..., None]
    return np.concatenate([*neighbours, columns, rows], axis=2).reshape(
        height * width, -1
    )


def _balanced_pixel_indexes(
    mask: np.ndarray,
    *,
    pixels_per_class: int,
    rng: np.random.Generator,
) -> np.ndarray:
    flattened = mask.reshape(-1)
    selected: list[np.ndarray] = []
    for class_id in range(len(VENUE_LABELS)):
        candidates = np.flatnonzero(flattened == class_id)
        if not len(candidates):
            raise ValueError(f"synthetic scene is missing class {class_id}")
        selected.append(
            rng.choice(
                candidates,
                size=pixels_per_class,
                replace=len(candidates) < pixels_per_class,
            )
        )
    return np.concatenate(selected)


def build_pixel_split(
    split: str,
    records: list[VenueSceneRecord],
    *,
    image_size: int = 48,
    pixels_per_class: int = 24,
    sampling_seed: int = 20260819,
) -> ModelSplit:
    selected_records = [record for record in records if record.split == split]
    if not selected_records:
        raise ValueError(f"venue split {split!r} is empty")
    feature_rows: list[np.ndarray] = []
    target_rows: list[np.ndarray] = []
    pixel_ids: list[str] = []
    rng = np.random.default_rng(
        sampling_seed + {"train": 1, "validation": 2, "test": 3}[split]
    )
    for record in selected_records:
        image, mask = render_synthetic_scene(record.seed, size=image_size)
        features = extract_pixel_features(image)
        indexes = _balanced_pixel_indexes(
            mask,
            pixels_per_class=pixels_per_class,
            rng=rng,
        )
        feature_rows.append(features[indexes])
        target_rows.append(mask.reshape(-1)[indexes])
        pixel_ids.extend(
            f"{record.scene_id}:sample-{sample_index:04d}"
            for sample_index in range(len(indexes))
        )
    matrix = np.concatenate(feature_rows).astype(np.float64)
    targets = np.concatenate(target_rows).astype(np.int64)
    return ModelSplit(
        name=split,
        scenario_ids=tuple(pixel_ids),
        features=matrix,
        targets={"segmentation": targets},
    )


def main() -> int:
    records = write_dataset_contract()
    counts = {
        split: sum(record.split == split for record in records)
        for split in ("train", "validation", "test")
    }
    print(
        "PASS: prepared deterministic venue-vision contract; "
        f"train={counts['train']}, validation={counts['validation']}, test={counts['test']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
