"""Register manually downloaded Gemini venue images with strict provenance.

This importer does not create or alter raw images. It reads the local raw-image
folder, validates the expected 12 sequential BakeSmart Gemini files, calculates
checksums and pixel metadata, and writes a provenance manifest outside the
ignored raw-data directory.

The exact prompt used for each image must be present in the metadata CSV. Blank
prompts are rejected. Every imported image remains synthetic and blocked from
training until seven-class mask annotation and human review are completed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import mimetypes
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_IMAGES_DIR = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "raw"
    / "gemini_synthetic_v1"
    / "images"
)
DEFAULT_METADATA_PATH = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "manifests"
    / "gemini_synthetic_v1_manual_metadata.csv"
)
DEFAULT_MANIFEST_PATH = (
    PROJECT_DIR
    / "data"
    / "venue_vision"
    / "manifests"
    / "gemini_synthetic_v1_manifest.csv"
)

EXPECTED_COUNT = 12
SUPPORTED_EXTENSIONS = {".jfif", ".jpg", ".jpeg", ".png"}
METADATA_COLUMNS = (
    "generation_id",
    "prompt_index",
    "provider",
    "model",
    "generated_at",
    "generated_at_precision",
    "prompt",
    "review",
)
MANIFEST_COLUMNS = (
    "generation_id",
    "prompt_index",
    "prompt_sha256",
    "provider",
    "model",
    "generated_at",
    "generated_at_precision",
    "synthetic_status",
    "training_status",
    "prompt",
    "image_path",
    "image_sha256",
    "mime_type",
    "pixel_width",
    "pixel_height",
    "review",
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_metadata(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"metadata CSV is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != METADATA_COLUMNS:
            raise ValueError(
                "manual Gemini metadata has an unexpected schema; expected: "
                + ",".join(METADATA_COLUMNS)
            )
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    if len(rows) != EXPECTED_COUNT:
        raise ValueError(
            f"metadata must contain exactly {EXPECTED_COUNT} rows; found {len(rows)}"
        )
    return rows


def _validate_metadata(rows: list[dict[str, str]]) -> None:
    seen_ids: set[str] = set()
    seen_indexes: set[int] = set()
    for expected_index, row in enumerate(rows, start=1):
        generation_id = row["generation_id"]
        expected_id = f"gemini-venue-{expected_index:04d}"
        if generation_id != expected_id:
            raise ValueError(
                f"metadata row {expected_index} generation_id must be {expected_id}; "
                f"found {generation_id or '<blank>'}"
            )
        try:
            prompt_index = int(row["prompt_index"])
        except ValueError as exc:
            raise ValueError(f"{generation_id} has an invalid prompt_index") from exc
        if prompt_index != expected_index:
            raise ValueError(f"{generation_id} prompt_index must be {expected_index}")
        if generation_id in seen_ids or prompt_index in seen_indexes:
            raise ValueError("manual Gemini metadata contains duplicate IDs or indexes")
        seen_ids.add(generation_id)
        seen_indexes.add(prompt_index)

        required = (
            "provider",
            "model",
            "generated_at",
            "generated_at_precision",
            "prompt",
            "review",
        )
        missing = [field for field in required if not row[field]]
        if missing:
            raise ValueError(
                f"{generation_id} is incomplete; fill exact provenance fields: "
                + ", ".join(missing)
            )
        if row["generated_at_precision"] not in {"datetime", "date"}:
            raise ValueError(
                f"{generation_id} generated_at_precision must be 'datetime' or 'date'"
            )
        if row["review"] not in {
            "ai_prescreen_pass_human_pending",
            "human_pending",
        }:
            raise ValueError(
                f"{generation_id} review must remain pending until a human review exists"
            )


def _image_for_generation(images_dir: Path, generation_id: str) -> Path:
    matches = sorted(
        path
        for path in images_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and path.stem.lower() == generation_id.lower()
    )
    if not matches:
        raise ValueError(f"raw image is missing for {generation_id}")
    if len(matches) > 1:
        raise ValueError(
            f"multiple raw image files match {generation_id}: "
            + ", ".join(path.name for path in matches)
        )
    return matches[0]


def _image_metadata(path: Path) -> tuple[bytes, str, int, int]:
    payload = path.read_bytes()
    try:
        with Image.open(path) as source:
            source.verify()
        with Image.open(path) as source:
            corrected = ImageOps.exif_transpose(source)
            width, height = corrected.size
            image_format = (source.format or "").upper()
    except (OSError, ValueError) as exc:
        raise ValueError(f"image is unreadable: {path.name}") from exc
    if width < 1 or height < 1:
        raise ValueError(f"image dimensions are invalid: {path.name}")
    mime_type = Image.MIME.get(image_format) or mimetypes.guess_type(path.name)[0]
    if mime_type not in {"image/jpeg", "image/png"}:
        raise ValueError(
            f"unsupported image content type for {path.name}: {mime_type or 'unknown'}"
        )
    return payload, mime_type, width, height


def build_manifest_rows(
    *,
    images_dir: Path,
    metadata_rows: list[dict[str, str]],
    project_dir: Path = PROJECT_DIR,
) -> list[dict[str, str]]:
    if not images_dir.is_dir():
        raise ValueError(f"raw image directory is missing: {images_dir}")
    _validate_metadata(metadata_rows)
    rows: list[dict[str, str]] = []
    for metadata in metadata_rows:
        image_path = _image_for_generation(images_dir, metadata["generation_id"])
        payload, mime_type, width, height = _image_metadata(image_path)
        try:
            relative_image_path = image_path.resolve().relative_to(project_dir.resolve())
        except ValueError as exc:
            raise ValueError("raw images must remain inside the bakesmart_ai project") from exc
        prompt = metadata["prompt"]
        rows.append(
            {
                "generation_id": metadata["generation_id"],
                "prompt_index": metadata["prompt_index"],
                "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
                "provider": metadata["provider"],
                "model": metadata["model"],
                "generated_at": metadata["generated_at"],
                "generated_at_precision": metadata["generated_at_precision"],
                "synthetic_status": "external_ai_generated",
                "training_status": "unlabelled_not_for_training",
                "prompt": prompt,
                "image_path": relative_image_path.as_posix(),
                "image_sha256": _sha256_bytes(payload),
                "mime_type": mime_type,
                "pixel_width": str(width),
                "pixel_height": str(height),
                "review": metadata["review"],
            }
        )
    return rows


def write_manifest(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    try:
        metadata_rows = _read_metadata(args.metadata)
        rows = build_manifest_rows(
            images_dir=args.images_dir,
            metadata_rows=metadata_rows,
        )
        if not args.check_only:
            write_manifest(args.output, rows)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1

    action = "validated" if args.check_only else "registered"
    print(
        f"PASS: {action} {len(rows)} manually generated Gemini venue images; "
        "all remain unlabelled_not_for_training"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
