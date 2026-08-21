"""Import CVAT Segmentation Mask exports into BakeSmart's venue dataset.

Expected input is CVAT's ``Segmentation Mask 1.1`` ZIP export. Human annotators
label only wall, floor, door, window, furniture and outlet. BakeSmart derives
class 6 (walkway candidate) from the interior of the labelled floor mask.

Run from ``bakesmart_ai``::

    python -m training.import_cvat_venue_masks \
        --archive D:/annotations/venue_masks.zip \
        --dataset real_v2 \
        --annotator-id sana-01
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from training.annotation_workspace import AnnotationWorkspace, UNLABELLED_ID
from training.venue_vision_data import LABEL_TO_ID
from training.walkway_generator import derive_walkway_candidate


MAX_ARCHIVE_MEMBERS = 5_000
MAX_MASK_BYTES = 64_000_000
CVAT_MANUAL_LABELS = ("wall", "floor", "door", "window", "furniture", "outlet")
BACKGROUND_LABELS = {
    "background",
    "unlabelled",
    "unlabeled",
    "unassigned",
    "ignore",
    "ignored",
}
LABEL_ALIASES = {
    "wall": "wall",
    "walls": "wall",
    "floor": "floor",
    "floors": "floor",
    "door": "door",
    "doors": "door",
    "window": "window",
    "windows": "window",
    "furniture": "furniture",
    "furnishing": "furniture",
    "furnishings": "furniture",
    "outlet": "outlet",
    "outlets": "outlet",
    "electrical outlet": "outlet",
    "electrical outlets": "outlet",
    "power outlet": "outlet",
    "power outlets": "outlet",
    "socket": "outlet",
    "sockets": "outlet",
    "power socket": "outlet",
    "power sockets": "outlet",
}


@dataclass(frozen=True)
class CvatLabel:
    index: int
    raw_name: str
    canonical_name: str | None
    rgb: tuple[int, int, int]


@dataclass(frozen=True)
class PreparedMask:
    scene_id: str
    member_name: str
    labels: np.ndarray
    status: str
    stats: dict[str, object]
    walkway: dict[str, object]


class CvatVenueMaskImporter:
    def __init__(self, workspace: AnnotationWorkspace | None = None) -> None:
        self.workspace = workspace or AnnotationWorkspace()

    def import_archive(
        self,
        archive_path: Path,
        *,
        dataset_key: str = "real_v2",
        annotator_id: str,
        replace_existing: bool = False,
        clearance_pixels: int | None = None,
        force_draft: bool = False,
        used_sam: bool = False,
        dry_run: bool = False,
    ) -> dict[str, object]:
        archive_path = Path(archive_path).expanduser().resolve()
        if not archive_path.is_file():
            raise FileNotFoundError(f"CVAT archive does not exist: {archive_path}")
        normalized_annotator = self.workspace._normalize_annotator_id(
            annotator_id,
            required=True,
        )
        archive_sha256 = self._sha256_file(archive_path)
        annotation_method = (
            "cvat_sam_assisted_import" if used_sam else "cvat_manual_import"
        )

        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                members = archive.infolist()
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise ValueError("CVAT archive contains too many files")
                labelmap_member = self._find_single_member(members, "labelmap.txt")
                if labelmap_member is None:
                    raise ValueError(
                        "CVAT Segmentation Mask export must include labelmap.txt for BakeSmart labels"
                    )
                labels = parse_labelmap(
                    archive.read(labelmap_member).decode("utf-8-sig")
                )
                self._validate_required_labels(labels)
                mask_members = self._segmentation_class_members(members)
                if not mask_members:
                    raise ValueError(
                        "CVAT archive contains no PNG masks under SegmentationClass/"
                    )
                prepared = [
                    self._prepare_mask(
                        archive,
                        member,
                        labels,
                        dataset_key=dataset_key,
                        replace_existing=replace_existing,
                        clearance_pixels=clearance_pixels,
                        force_draft=force_draft,
                    )
                    for member in mask_members
                ]
        except zipfile.BadZipFile as exc:
            raise ValueError("CVAT export is not a readable ZIP archive") from exc

        if not dry_run:
            for item in prepared:
                self._persist(
                    item,
                    dataset_key=dataset_key,
                    annotator_id=normalized_annotator,
                    archive_name=archive_path.name,
                    archive_sha256=archive_sha256,
                    annotation_method=annotation_method,
                )

        report = {
            "schema_version": 1,
            "import_format": "CVAT Segmentation Mask 1.1",
            "archive": archive_path.name,
            "archive_sha256": archive_sha256,
            "dataset": dataset_key,
            "annotator_id": normalized_annotator,
            "manual_labels": list(CVAT_MANUAL_LABELS),
            "annotation_method": annotation_method,
            "derived_label": "walkway",
            "dry_run": dry_run,
            "imported_scene_count": 0 if dry_run else len(prepared),
            "validated_scene_count": len(prepared),
            "complete_pending_review": sum(
                item.status == "annotation_complete_pending_review" for item in prepared
            ),
            "draft_in_progress": sum(item.status == "draft_in_progress" for item in prepared),
            "scenes": [
                {
                    "scene_id": item.scene_id,
                    "cvat_mask_member": item.member_name,
                    "status": item.status,
                    "unlabelled_pixels": item.stats["unlabelled_pixels"],
                    "walkway_pixels": item.walkway["walkway_pixels"],
                    "walkway_clearance_pixels": item.walkway["clearance_pixels"],
                }
                for item in prepared
            ],
            "notes": [
                "Walkway candidate is derived automatically from floor and is not manually annotated.",
                "Derived walkway is visual-only and does not prove 90 cm or any other metric clearance.",
                "Imported masks remain not_for_training until independent review approves them.",
            ],
        }
        if not dry_run:
            report_path = self._write_report(dataset_key, report)
            report["report_path"] = self.workspace._relative(report_path)
        return report

    def _prepare_mask(
        self,
        archive: zipfile.ZipFile,
        member: zipfile.ZipInfo,
        labelmap: list[CvatLabel],
        *,
        dataset_key: str,
        replace_existing: bool,
        clearance_pixels: int | None,
        force_draft: bool,
    ) -> PreparedMask:
        if member.file_size > MAX_MASK_BYTES:
            raise ValueError(f"CVAT mask is too large: {member.filename}")
        scene_id = scene_id_from_mask_member(member.filename)
        image_path = self.workspace.image_path(dataset_key, scene_id)
        mask_path = self.workspace.mask_path(dataset_key, scene_id)
        record = self.workspace.load_record(dataset_key, scene_id)
        if record and record.get("status") == "annotation_complete_pending_review":
            raise ValueError(
                f"{scene_id} is already complete and pending review; it cannot be overwritten by import"
            )
        if mask_path.is_file() and not replace_existing:
            raise ValueError(
                f"{scene_id} already has a local mask; use --replace-existing to replace a draft"
            )

        raw = archive.read(member)
        manual_labels, mask_size = decode_cvat_mask(raw, labelmap)
        with Image.open(image_path) as source:
            expected_size = ImageOps.exif_transpose(source).size
        if mask_size != expected_size:
            raise ValueError(
                f"{scene_id} mask is {mask_size[0]}x{mask_size[1]} but source image is "
                f"{expected_size[0]}x{expected_size[1]}"
            )

        walkway_result = derive_walkway_candidate(
            manual_labels,
            clearance_pixels=clearance_pixels,
        )
        stats = self.workspace.validate_labels(walkway_result.labels)
        status = (
            "draft_in_progress"
            if force_draft or not stats["complete"]
            else "annotation_complete_pending_review"
        )
        walkway = {
            "strategy": "floor_core_erosion_v1",
            "clearance_pixels": walkway_result.clearance_pixels,
            "floor_pixels_before": walkway_result.floor_pixels_before,
            "walkway_pixels": walkway_result.walkway_pixels,
            "walkway_components": walkway_result.walkway_components,
            "walkway_fraction_of_floor": walkway_result.walkway_fraction_of_floor,
            "visual_only_not_metric": True,
        }
        return PreparedMask(
            scene_id=scene_id,
            member_name=member.filename,
            labels=walkway_result.labels,
            status=status,
            stats=stats,
            walkway=walkway,
        )

    def _persist(
        self,
        item: PreparedMask,
        *,
        dataset_key: str,
        annotator_id: str,
        archive_name: str,
        archive_sha256: str,
        annotation_method: str,
    ) -> None:
        self.workspace._save_mask(dataset_key, item.scene_id, item.labels)
        completed_at = (
            self.workspace._utc_now()
            if item.status == "annotation_complete_pending_review"
            else None
        )
        record = self.workspace._record(
            dataset_key=dataset_key,
            scene_id=item.scene_id,
            annotator_id=annotator_id,
            status=item.status,
            annotation_completed_at=completed_at,
        )
        record.update(
            {
                "annotation_method": annotation_method,
                "source_annotation_tool": "CVAT",
                "source_annotation_format": "Segmentation Mask 1.1",
                "source_archive_name": archive_name,
                "source_archive_sha256": archive_sha256,
                "source_mask_member": item.member_name,
                "manual_label_classes": list(CVAT_MANUAL_LABELS),
                "walkway_annotation_method": "derived_from_floor",
                "walkway_generation": item.walkway,
                "training_status": "not_for_training",
            }
        )
        self.workspace._write_record(dataset_key, item.scene_id, record)

    def _write_report(self, dataset_key: str, report: dict[str, object]) -> Path:
        dataset = self.workspace._dataset(dataset_key)
        report_dir = dataset.records_dir / "cvat_imports"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.workspace._utc_now().replace(":", "-")
        path = report_dir / f"cvat-import-{stamp}.json"
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _find_single_member(
        members: list[zipfile.ZipInfo],
        filename: str,
    ) -> zipfile.ZipInfo | None:
        matches = [
            member
            for member in members
            if not member.is_dir()
            and PurePosixPath(member.filename).name.lower() == filename.lower()
        ]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"CVAT archive contains multiple {filename} files")
        return matches[0]

    @staticmethod
    def _segmentation_class_members(
        members: list[zipfile.ZipInfo],
    ) -> list[zipfile.ZipInfo]:
        selected = []
        seen_scene_ids: set[str] = set()
        for member in members:
            if member.is_dir() or not member.filename.lower().endswith(".png"):
                continue
            parts = [part.lower() for part in PurePosixPath(member.filename).parts]
            if "segmentationclass" not in parts:
                continue
            scene_id = scene_id_from_mask_member(member.filename)
            if scene_id in seen_scene_ids:
                raise ValueError(f"duplicate CVAT class mask for scene {scene_id}")
            seen_scene_ids.add(scene_id)
            selected.append(member)
        return sorted(selected, key=lambda member: member.filename)

    @staticmethod
    def _validate_required_labels(labels: list[CvatLabel]) -> None:
        canonical = {entry.canonical_name for entry in labels if entry.canonical_name}
        missing = set(CVAT_MANUAL_LABELS) - canonical
        if missing:
            raise ValueError(
                "CVAT labelmap is missing required BakeSmart labels: "
                + ", ".join(sorted(missing))
            )

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


def scene_id_from_mask_member(member_name: str) -> str:
    scene_id = PurePosixPath(member_name).stem
    lowered = scene_id.lower()
    for suffix in (".jpg", ".jpeg", ".png"):
        if lowered.endswith(suffix):
            scene_id = scene_id[: -len(suffix)]
            break
    return scene_id


def canonical_label_name(raw_name: str) -> str | None:
    normalized = " ".join(raw_name.strip().lower().replace("_", " ").split())
    if normalized in BACKGROUND_LABELS or normalized.startswith("_dummy"):
        return None
    if "walkway" in normalized:
        raise ValueError(
            "Do not annotate Walkway in CVAT. BakeSmart derives walkway automatically from Floor."
        )
    try:
        return LABEL_ALIASES[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported CVAT label: {raw_name!r}") from exc


def parse_labelmap(text: str) -> list[CvatLabel]:
    entries: list[CvatLabel] = []
    seen_names: set[str] = set()
    seen_colours: set[tuple[int, int, int]] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].rstrip()
        parts = line.split(":")
        if len(parts) < 2:
            raise ValueError(f"invalid CVAT labelmap line: {raw_line!r}")
        raw_name = parts[0].strip()
        colour_parts = [part.strip() for part in parts[1].split(",")]
        if len(colour_parts) != 3:
            raise ValueError(f"invalid RGB colour in CVAT labelmap: {raw_line!r}")
        try:
            rgb = tuple(int(value) for value in colour_parts)
        except ValueError as exc:
            raise ValueError(f"invalid RGB colour in CVAT labelmap: {raw_line!r}") from exc
        if any(value < 0 or value > 255 for value in rgb):
            raise ValueError(f"CVAT labelmap RGB values must be 0-255: {raw_line!r}")
        if raw_name.lower() in seen_names:
            raise ValueError(f"duplicate CVAT label name: {raw_name}")
        if rgb in seen_colours:
            raise ValueError(f"duplicate CVAT label colour: {rgb}")
        seen_names.add(raw_name.lower())
        seen_colours.add(rgb)
        entries.append(
            CvatLabel(
                index=len(entries),
                raw_name=raw_name,
                canonical_name=canonical_label_name(raw_name),
                rgb=rgb,
            )
        )
    if not entries:
        raise ValueError("CVAT labelmap.txt is empty")
    return entries


def decode_cvat_mask(
    raw_png: bytes,
    labelmap: list[CvatLabel],
) -> tuple[np.ndarray, tuple[int, int]]:
    if not raw_png or len(raw_png) > MAX_MASK_BYTES:
        raise ValueError("CVAT mask PNG is empty or too large")
    try:
        with Image.open(io.BytesIO(raw_png)) as source:
            if source.format != "PNG":
                raise ValueError("CVAT SegmentationClass mask must be PNG")
            size = source.size
            if source.mode in {"1", "L", "I", "I;16", "I;16B", "I;16L"}:
                indexes = np.asarray(source, dtype=np.int64)
                labels = _decode_index_mask(indexes, labelmap)
            else:
                rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
                labels = _decode_rgb_mask(rgb, labelmap)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("CVAT mask is not a readable PNG") from exc
    return labels, size


def _decode_index_mask(indexes: np.ndarray, labelmap: list[CvatLabel]) -> np.ndarray:
    if indexes.ndim != 2:
        raise ValueError("indexed CVAT mask must be single-channel")
    output = np.full(indexes.shape, UNLABELLED_ID, dtype=np.uint8)
    unique_indexes = [int(value) for value in np.unique(indexes)]
    for index in unique_indexes:
        if index < 0 or index >= len(labelmap):
            raise ValueError(
                f"CVAT grayscale mask uses index {index} but labelmap has {len(labelmap)} entries"
            )
        canonical = labelmap[index].canonical_name
        if canonical is None:
            continue
        output[indexes == index] = LABEL_TO_ID[canonical]
    return output


def _decode_rgb_mask(rgb: np.ndarray, labelmap: list[CvatLabel]) -> np.ndarray:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("RGB CVAT mask must have three colour channels")
    output = np.full(rgb.shape[:2], UNLABELLED_ID, dtype=np.uint8)
    colour_to_label = {entry.rgb: entry.canonical_name for entry in labelmap}
    flat = rgb.reshape(-1, 3)
    unique_colours = np.unique(flat, axis=0)
    for colour_array in unique_colours:
        colour = tuple(int(value) for value in colour_array)
        if colour not in colour_to_label:
            if colour == (0, 0, 0):
                continue
            raise ValueError(f"CVAT mask contains colour {colour} not declared in labelmap.txt")
        canonical = colour_to_label[colour]
        if canonical is None:
            continue
        selected = np.all(rgb == np.asarray(colour, dtype=np.uint8), axis=2)
        output[selected] = LABEL_TO_ID[canonical]
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        default="real_v2",
        choices=("real_v2", "gemini_synthetic_v1"),
    )
    parser.add_argument("--annotator-id", required=True)
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--clearance-pixels", type=int)
    parser.add_argument(
        "--force-draft",
        action="store_true",
        help="Keep fully-labelled imports as drafts instead of pending review.",
    )
    parser.add_argument(
        "--used-sam",
        action="store_true",
        help="Record that CVAT SAM/SAM2 assistance was actually used.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.clearance_pixels is not None and args.clearance_pixels < 0:
        parser.error("--clearance-pixels must be >= 0")
    report = CvatVenueMaskImporter().import_archive(
        args.archive,
        dataset_key=args.dataset,
        annotator_id=args.annotator_id,
        replace_existing=args.replace_existing,
        clearance_pixels=args.clearance_pixels,
        force_draft=args.force_draft,
        used_sam=args.used_sam,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
