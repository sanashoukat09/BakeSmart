"""Create review-ready automatic draft masks for BakeSmart real venue photos.

This helper uses a pretrained SegFormer ADE20K ONNX model only to accelerate
annotation. The final BakeSmart venue model remains separate and is trained on
human-reviewed BakeSmart masks.

New drafts use semantic IDs 0-5 only. Walkway is derived from Floor and saved as
a separate binary mask so Floor pixels are never replaced by Walkway.

Run from bakesmart_ai:
    python -m training.auto_label_real_venues
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PIL import Image, ImageOps

from training.annotation_workspace import PROJECT_DIR, UNLABELLED_ID
from training.auto_label_mapping import map_ade20k_to_bakesmart, mapping_coverage
from training.semantic_annotation_workspace import SemanticAnnotationWorkspace
from training.walkway_generator import derive_walkway_candidate

MODEL_NAME = "Xenova/segformer-b0-finetuned-ade-512-512"
MODEL_VERSION = "segformer-b0-ade20k-onnx-v1"
MODEL_URL = (
    "https://huggingface.co/Xenova/segformer-b0-finetuned-ade-512-512/"
    "resolve/main/onnx/model.onnx?download=true"
)
DEFAULT_MODEL_PATH = PROJECT_DIR / "models" / "annotation_helpers" / "segformer_ade20k" / "model.onnx"
INPUT_SIZE = 512
IMAGE_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True)
class AutoLabelPrediction:
    labels: np.ndarray
    pixel_confidence: np.ndarray
    mean_confidence: float
    direct_mapping_fraction: float


class PredictionEngine(Protocol):
    model_version: str

    def predict(self, image: Image.Image) -> AutoLabelPrediction: ...


class SegformerOnnxEngine:
    model_version = MODEL_VERSION

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH, *, allow_download: bool = True) -> None:
        self.model_path = Path(model_path)
        self.allow_download = allow_download
        self._session = None

    def _active_session(self):
        if self._session is not None:
            return self._session
        model_path = ensure_model(self.model_path, allow_download=self.allow_download)
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("onnxruntime is missing. Run: pip install -r requirements.txt") from exc
        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        return self._session

    def predict(self, image: Image.Image) -> AutoLabelPrediction:
        session = self._active_session()
        source = image.convert("RGB")
        width, height = source.size
        resized = source.resize((INPUT_SIZE, INPUT_SIZE), Image.Resampling.BILINEAR)
        pixels = np.asarray(resized, dtype=np.float32) / 255.0
        normalized = (pixels - IMAGE_MEAN) / IMAGE_STD
        tensor = np.transpose(normalized, (2, 0, 1))[None].astype(np.float32)
        logits = np.asarray(
            session.run([session.get_outputs()[0].name], {session.get_inputs()[0].name: tensor})[0]
        )
        if logits.ndim != 4 or logits.shape[0] != 1:
            raise ValueError(f"unexpected annotation-model output shape: {logits.shape}")
        logits = logits[0]
        if logits.shape[0] == 150:
            class_logits = logits
        elif logits.shape[-1] == 150:
            class_logits = np.transpose(logits, (2, 0, 1))
        else:
            raise ValueError(f"annotation-model output has no 150-class ADE20K axis: {logits.shape}")

        maximum = np.max(class_logits, axis=0, keepdims=True)
        exponentials = np.exp(class_logits - maximum)
        probabilities = exponentials / np.sum(exponentials, axis=0, keepdims=True)
        confidence = np.max(probabilities, axis=0).astype(np.float32)

        logits_hwc = np.transpose(class_logits.astype(np.float32), (1, 2, 0))
        if logits_hwc.shape[:2] != (INPUT_SIZE, INPUT_SIZE):
            logits_hwc = cv2.resize(logits_hwc, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
        ade_ids = np.argmax(logits_hwc, axis=2).astype(np.uint8)

        ade_full = np.asarray(
            Image.fromarray(ade_ids, mode="L").resize((width, height), Image.Resampling.NEAREST),
            dtype=np.uint8,
        )
        confidence_full = np.asarray(
            Image.fromarray(confidence, mode="F").resize((width, height), Image.Resampling.BILINEAR),
            dtype=np.float32,
        )
        labels = map_ade20k_to_bakesmart(ade_full)
        mapped = labels != UNLABELLED_ID
        mean_confidence = float(np.mean(confidence_full[mapped])) if np.any(mapped) else 0.0
        return AutoLabelPrediction(
            labels=labels,
            pixel_confidence=confidence_full,
            mean_confidence=mean_confidence,
            direct_mapping_fraction=mapping_coverage(labels),
        )


class BatchVenueAutoLabeller:
    def __init__(self, workspace: SemanticAnnotationWorkspace | None = None, engine: PredictionEngine | None = None) -> None:
        self.workspace = workspace or SemanticAnnotationWorkspace()
        self.engine = engine or SegformerOnnxEngine()

    def run(
        self,
        *,
        dataset_key: str = "real_v2",
        replace_existing: bool = False,
        limit: int | None = None,
        scene_ids: set[str] | None = None,
        annotator_id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, object]:
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1")
        annotator = self.workspace._normalize_annotator_id(annotator_id, required=False)  # noqa: SLF001
        scenes = self.workspace.list_scenes(dataset_key)
        if scene_ids:
            known = {item["scene_id"] for item in scenes}
            unknown = scene_ids - known
            if unknown:
                raise ValueError("unknown scene ID(s): " + ", ".join(sorted(unknown)))
            scenes = [item for item in scenes if item["scene_id"] in scene_ids]
        if limit is not None:
            scenes = scenes[:limit]

        results = []
        for index, descriptor in enumerate(scenes, 1):
            scene_id = str(descriptor["scene_id"])
            print(f"[{index}/{len(scenes)}] {scene_id}", flush=True)
            result = self._process_scene(dataset_key, scene_id, replace_existing, annotator, dry_run)
            results.append(result)
            print(f"    {result['action']}: {result.get('review_priority', result.get('reason', ''))}", flush=True)

        processed = [item for item in results if item["action"] == "auto_labelled"]
        report = {
            "schema_version": 2,
            "dataset": dataset_key,
            "semantic_schema": "six_visual_classes_v2",
            "walkway_storage": "separate_binary_mask",
            "model_name": MODEL_NAME,
            "model_version": self.engine.model_version,
            "annotation_method": "pretrained_scene_model_draft_then_human_review",
            "final_bakesmart_model_dependency": False,
            "dry_run": dry_run,
            "requested_scene_count": len(scenes),
            "auto_labelled_scene_count": len(processed),
            "skipped_scene_count": len(results) - len(processed),
            "quick_review_count": sum(x.get("review_priority") == "quick_review" for x in processed),
            "needs_attention_count": sum(x.get("review_priority") == "needs_attention" for x in processed),
            "outlet_note": "Outlet is not predicted by this helper; add it manually only when clearly visible.",
            "scenes": results,
        }
        if not dry_run:
            report_path = self._write_report(dataset_key, report)
            report["report_path"] = self.workspace._relative(report_path)  # noqa: SLF001
        return report

    def _process_scene(self, dataset_key, scene_id, replace_existing, annotator_id, dry_run):
        record = self.workspace.load_record(dataset_key, scene_id)
        if record and record.get("status") == "annotation_complete_pending_review":
            return {"scene_id": scene_id, "action": "skipped", "reason": "already_complete_pending_review"}
        if self.workspace.mask_path(dataset_key, scene_id).is_file() and not replace_existing:
            return {"scene_id": scene_id, "action": "skipped", "reason": "existing_mask_use_--replace-existing"}

        with Image.open(self.workspace.image_path(dataset_key, scene_id)) as source:
            prediction = self.engine.predict(ImageOps.exif_transpose(source).convert("RGB"))
        walkway = derive_walkway_candidate(prediction.labels)
        semantic_labels = walkway.semantic_labels
        stats = self.workspace.validate_labels(semantic_labels)
        score = float(np.clip(0.65 * prediction.mean_confidence + 0.35 * prediction.direct_mapping_fraction, 0, 1))
        priority = "quick_review" if score >= 0.72 and prediction.direct_mapping_fraction >= 0.82 else "needs_attention"
        result = {
            "scene_id": scene_id,
            "action": "auto_labelled",
            "review_priority": priority,
            "review_score": round(score, 4),
            "mean_model_confidence": round(prediction.mean_confidence, 4),
            "direct_mapping_fraction": round(prediction.direct_mapping_fraction, 4),
            "coverage_fraction": stats["coverage_fraction"],
            "unlabelled_pixels": stats["unlabelled_pixels"],
            "class_counts": stats["class_counts"],
            "walkway_pixels": walkway.walkway_pixels,
        }
        if dry_run:
            return result

        self.workspace._save_mask(dataset_key, scene_id, semantic_labels)  # noqa: SLF001
        self.workspace._save_walkway_mask(dataset_key, scene_id, walkway.walkway_mask)  # noqa: SLF001
        auto_record = self.workspace._record(  # noqa: SLF001
            dataset_key=dataset_key,
            scene_id=scene_id,
            annotator_id=annotator_id,
            status="draft_in_progress",
            annotation_completed_at=None,
        )
        auto_record.update({
            "annotation_method": "pretrained_scene_model_draft",
            "annotation_helper_model": MODEL_NAME,
            "annotation_helper_model_version": self.engine.model_version,
            "annotation_helper_is_final_model": False,
            "human_review_required": True,
            "auto_label_review_priority": priority,
            "auto_label_review_score": round(score, 4),
            "auto_label_mean_confidence": round(prediction.mean_confidence, 4),
            "auto_label_direct_mapping_fraction": round(prediction.direct_mapping_fraction, 4),
            "semantic_schema_version": 2,
            "semantic_class_ids": [0, 1, 2, 3, 4, 5],
            "walkway_annotation_method": "derived_from_floor_separate_binary_mask",
            "walkway_mask_path": self.workspace._relative(self.workspace.walkway_path(dataset_key, scene_id)),  # noqa: SLF001
            "walkway_mask_sha256": self.workspace._sha256_file(self.workspace.walkway_path(dataset_key, scene_id)),  # noqa: SLF001
            "outlet_annotation_method": "manual_if_visible",
            "training_status": "not_for_training",
        })
        self.workspace._write_record(dataset_key, scene_id, auto_record)  # noqa: SLF001
        self._write_scene_provenance(dataset_key, scene_id, auto_record, result)
        return result

    def _helper_model_sha256(self) -> str | None:
        path = getattr(self.engine, "model_path", None)
        return sha256_file(Path(path)) if path and Path(path).is_file() else None

    def _write_scene_provenance(self, dataset_key, scene_id, record, result):
        path = self.workspace.record_path(dataset_key, scene_id).with_name(f"{scene_id}.autolabel.json")
        payload = {
            "schema_version": 2,
            "dataset": dataset_key,
            "scene_id": scene_id,
            "semantic_schema": "six_visual_classes_v2",
            "walkway_storage": "separate_binary_mask",
            "annotation_helper_model": MODEL_NAME,
            "annotation_helper_model_version": self.engine.model_version,
            "annotation_helper_model_sha256": self._helper_model_sha256(),
            "annotation_helper_is_final_model": False,
            "human_review_required": True,
            "image_sha256": record["image_sha256"],
            "suggested_mask_sha256": record["mask_sha256"],
            "walkway_mask_sha256": record.get("walkway_mask_sha256"),
            "generated_at": record["updated_at"],
            "training_status": "not_for_training",
            **result,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_report(self, dataset_key, report):
        dataset = self.workspace._dataset(dataset_key)  # noqa: SLF001
        directory = dataset.records_dir / "auto_label_runs"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = self.workspace._utc_now().replace(":", "-")  # noqa: SLF001
        path = directory / f"auto-label-{stamp}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


def ensure_model(path: Path, *, allow_download: bool = True) -> Path:
    path = Path(path)
    if path.is_file() and path.stat().st_size > 1_000_000:
        return path
    path.unlink(missing_ok=True)
    if not allow_download:
        raise FileNotFoundError(f"annotation helper model is missing: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".onnx.part")
    print("First run: downloading the venue annotation helper model...", flush=True)
    request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "BakeSmart-FYP/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                downloaded += len(block)
                if total:
                    print(f"    downloaded {downloaded * 100 // total}%", flush=True)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Could not download the annotation helper model. Check internet and run again.") from exc
    if temporary.stat().st_size <= 1_000_000:
        temporary.unlink(missing_ok=True)
        raise ValueError("downloaded annotation helper model file is unexpectedly small")
    temporary.replace(path)
    print(f"Annotation helper model ready: {path}", flush=True)
    print(f"Model SHA256: {sha256_file(path)}", flush=True)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="real_v2")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--annotator-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args()
    try:
        report = BatchVenueAutoLabeller(
            engine=SegformerOnnxEngine(allow_download=not args.no_download)
        ).run(
            dataset_key=args.dataset,
            replace_existing=args.replace_existing,
            limit=args.limit,
            scene_ids=set(args.scene_id) or None,
            annotator_id=args.annotator_id,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("\nBakeSmart auto-labelling finished.")
    print(f"Auto-labelled: {report['auto_labelled_scene_count']}")
    print(f"Quick review: {report['quick_review_count']}")
    print(f"Needs attention: {report['needs_attention_count']}")
    print(f"Skipped: {report['skipped_scene_count']}")
    if report.get("report_path"):
        print(f"Report: {report['report_path']}")
    print("Next: open the BakeSmart labeller, review the six semantic classes, optionally view Walkway, then complete them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
