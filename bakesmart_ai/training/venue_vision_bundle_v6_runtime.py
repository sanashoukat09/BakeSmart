"""Validation-only runtime for the v5 room segmenter plus v6 Door detector."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    import torch
    from torchvision.models.detection import fasterrcnn_mobilenet_v3_large_320_fpn
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyTorch and torchvision are required for the v6 venue runtime") from exc

from training.annotation_workspace import PROJECT_DIR
from training.finalize_real_venue_v6_bundle import DEFAULT_OUTPUT_DIR, MODEL_VERSION
from training.real_venue_segmentation import CLASS_NAMES, sha256_file
from training.train_real_venue_segmentation_v5 import BakeSmartLRASPP
from training.venue_vision_runtime import VenueVisionCandidate


SEGMENTATION_CLASSES = ("wall", "floor", "window", "furniture")
MINIMUM_COMPONENT_FRACTION = {
    "wall": 0.06,
    "floor": 0.04,
    "window": 0.006,
    "furniture": 0.006,
    "walkway": 0.02,
}


class VenueVisionBundleV6Runtime:
    """Return only unconfirmed 2D candidates; never create measured obstacles."""

    def __init__(
        self,
        *,
        segmentation_model: torch.nn.Module,
        door_model: torch.nn.Module,
        manifest: dict[str, object],
        device: torch.device,
    ) -> None:
        self.segmentation_model = segmentation_model.eval()
        self.door_model = door_model.eval()
        self.manifest = manifest
        self.device = device
        self.model_version = str(manifest["model_version"])
        self.maximum_confidence = min(
            float(manifest["runtime_policy"]["maximum_reported_confidence"]), 0.49
        )
        self.door_score_threshold = float(
            manifest["runtime_policy"]["door_score_threshold"]
        )
        # v5 was trained on 320x320 views. The validation-only runtime needs
        # responsive CPU inference, so use one training-sized forward pass
        # instead of the nine overlapping tiles used for offline validation.
        policy = manifest["runtime_policy"]
        self.canvas_size = int(policy.get("segmentation_canvas_size", 320))
        if self.canvas_size < 256 or self.canvas_size > 640:
            raise ValueError("v6 runtime segmentation canvas must be 256-640 pixels")

    @classmethod
    def load(
        cls,
        bundle_dir: Path = DEFAULT_OUTPUT_DIR,
        *,
        device_name: str = "cpu",
    ) -> "VenueVisionBundleV6Runtime":
        bundle_dir = Path(bundle_dir).resolve()
        manifest_path = bundle_dir / "bundle_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("v6 bundle manifest root must be a JSON object")
        if manifest.get("model_version") != MODEL_VERSION:
            raise ValueError("v6 bundle has an unexpected model version")
        if manifest.get("status") != "validation_only_unconfirmed_runtime":
            raise ValueError("v6 bundle is not approved for unconfirmed runtime use")
        if manifest.get("production_ready") is not False:
            raise ValueError("v6 bundle must remain production_ready=false")
        if manifest.get("locked_test_used") is not False:
            raise ValueError("v6 bundle must confirm locked_test_used=false")
        policy = manifest.get("runtime_policy")
        if not isinstance(policy, dict):
            raise ValueError("v6 bundle has no runtime policy")
        if policy.get("all_candidates_require_customer_confirmation") is not True:
            raise ValueError("v6 bundle must require candidate confirmation")
        if policy.get("outlet_mode") != "customer_manual":
            raise ValueError("v6 bundle must keep Outlet marking manual")
        if device_name not in {"cpu", "cuda"}:
            raise ValueError("runtime device must be cpu or cuda")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA runtime requested but unavailable")
        device = torch.device(device_name)
        segmentation_info = manifest.get("segmentation")
        door_info = manifest.get("door")
        if not isinstance(segmentation_info, dict) or not isinstance(door_info, dict):
            raise ValueError("v6 bundle artifact metadata is incomplete")
        segmentation_path = bundle_dir / str(segmentation_info["checkpoint"])
        door_path = bundle_dir / str(door_info["checkpoint"])
        for path, info, label in (
            (segmentation_path, segmentation_info, "segmentation"),
            (door_path, door_info, "Door"),
        ):
            if not path.is_file():
                raise FileNotFoundError(path)
            if sha256_file(path) != info.get("checkpoint_sha256"):
                raise ValueError(f"v6 {label} checkpoint checksum is invalid")

        segmentation_payload = torch.load(
            segmentation_path, map_location=device, weights_only=False
        )
        door_payload = torch.load(door_path, map_location=device, weights_only=False)
        if segmentation_payload.get("model_name") != "BakeSmartLRASPP":
            raise ValueError("v6 segmentation checkpoint model is invalid")
        if door_payload.get("model_name") != "BakeSmartDoorDetectorV6":
            raise ValueError("v6 Door checkpoint model is invalid")
        if segmentation_payload.get("test_data_used") is not False:
            raise ValueError("v6 segmentation checkpoint test flag is invalid")
        if door_payload.get("test_data_used") is not False:
            raise ValueError("v6 Door checkpoint test flag is invalid")

        segmentation_model = BakeSmartLRASPP(pretrained=False).to(device)
        segmentation_model.load_state_dict(
            segmentation_payload["model_state_dict"], strict=True
        )
        door_model = fasterrcnn_mobilenet_v3_large_320_fpn(
            weights=None,
            weights_backbone=None,
            min_size=384,
            max_size=640,
            box_score_thresh=float(policy["door_score_threshold"]),
        )
        features = door_model.roi_heads.box_predictor.cls_score.in_features
        door_model.roi_heads.box_predictor = FastRCNNPredictor(features, 2)
        door_model.load_state_dict(door_payload["model_state_dict"], strict=True)
        door_model.to(device)
        return cls(
            segmentation_model=segmentation_model,
            door_model=door_model,
            manifest=manifest,
            device=device,
        )

    @torch.no_grad()
    def candidates(self, image: Image.Image) -> list[VenueVisionCandidate]:
        rgb = image.convert("RGB")
        segmentation = self._segmentation_candidates(rgb)
        doors = self._door_candidates(rgb)
        candidates = segmentation + doors
        candidates.sort(
            key=lambda item: (item.confidence, item.area_fraction), reverse=True
        )
        return candidates[:10]

    def _segmentation_candidates(self, image: Image.Image) -> list[VenueVisionCandidate]:
        width, height = image.size
        scale = min(self.canvas_size / width, self.canvas_size / height)
        resized_width = max(1, int(round(width * scale)))
        resized_height = max(1, int(round(height * scale)))
        resized = image.resize((resized_width, resized_height), Image.Resampling.BILINEAR)
        canvas = Image.new("RGB", (self.canvas_size, self.canvas_size), (127, 127, 127))
        left = (self.canvas_size - resized_width) // 2
        top = (self.canvas_size - resized_height) // 2
        canvas.paste(resized, (left, top))
        pixels = np.asarray(canvas, dtype=np.float32) / 255.0
        pixels = (
            pixels - np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
        ) / np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = torch.from_numpy(pixels.transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        logits = self.segmentation_model(tensor)
        if not isinstance(logits, torch.Tensor) or logits.ndim != 4:
            raise ValueError("v6 segmentation model returned invalid logits")
        probabilities = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()
        probabilities = probabilities[
            :, top : top + resized_height, left : left + resized_width
        ]
        prediction = np.argmax(probabilities, axis=0).astype(np.uint8)
        total = max(1, resized_width * resized_height)
        candidates: list[VenueVisionCandidate] = []
        floor_mask: np.ndarray | None = None
        for label in SEGMENTATION_CLASSES:
            class_id = CLASS_NAMES.index(label)
            binary = (prediction == class_id).astype(np.uint8)
            if label == "floor":
                floor_mask = binary
            candidates.extend(
                self._component_candidates(
                    binary,
                    label=label,
                    class_id=class_id,
                    probabilities=probabilities,
                    minimum=max(1, round(MINIMUM_COMPONENT_FRACTION[label] * total)),
                    limit=2,
                )
            )
        if floor_mask is not None:
            lower_floor = floor_mask.copy()
            lower_floor[: int(round(resized_height * 0.45)), :] = 0
            candidates.extend(
                self._component_candidates(
                    lower_floor,
                    label="walkway",
                    class_id=CLASS_NAMES.index("floor"),
                    probabilities=probabilities,
                    minimum=max(1, round(MINIMUM_COMPONENT_FRACTION["walkway"] * total)),
                    limit=1,
                    confidence_scale=0.80,
                )
            )
        return candidates

    def _component_candidates(
        self,
        binary: np.ndarray,
        *,
        label: str,
        class_id: int,
        probabilities: np.ndarray,
        minimum: int,
        limit: int,
        confidence_scale: float = 1.0,
    ) -> list[VenueVisionCandidate]:
        count, components, stats, _centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )
        order = sorted(
            range(1, count),
            key=lambda index: int(stats[index, cv2.CC_STAT_AREA]),
            reverse=True,
        )
        height, width = binary.shape
        result: list[VenueVisionCandidate] = []
        for component in order:
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < minimum:
                continue
            x = int(stats[component, cv2.CC_STAT_LEFT])
            y = int(stats[component, cv2.CC_STAT_TOP])
            box_width = int(stats[component, cv2.CC_STAT_WIDTH])
            box_height = int(stats[component, cv2.CC_STAT_HEIGHT])
            component_mask = components == component
            raw_confidence = float(np.mean(probabilities[class_id][component_mask]))
            result.append(
                VenueVisionCandidate(
                    label=label,
                    confidence=round(
                        min(raw_confidence * confidence_scale, self.maximum_confidence), 4
                    ),
                    bounding_box=(
                        round(x / width, 4),
                        round(y / height, 4),
                        round(box_width / width, 4),
                        round(box_height / height, 4),
                    ),
                    area_fraction=round(area / (width * height), 4),
                )
            )
            if len(result) >= limit:
                break
        return result

    def _door_candidates(self, image: Image.Image) -> list[VenueVisionCandidate]:
        pixels = np.array(image, dtype=np.float32, copy=True) / 255.0
        tensor = torch.from_numpy(pixels.transpose(2, 0, 1)).float().to(self.device)
        output = self.door_model([tensor])[0]
        width, height = image.size
        candidates: list[VenueVisionCandidate] = []
        for box, score in zip(output["boxes"], output["scores"]):
            raw_score = float(score.detach().cpu())
            if raw_score < self.door_score_threshold:
                continue
            x0, y0, x1, y1 = [float(value) for value in box.detach().cpu()]
            x0 = min(max(x0, 0.0), float(width))
            y0 = min(max(y0, 0.0), float(height))
            x1 = min(max(x1, x0), float(width))
            y1 = min(max(y1, y0), float(height))
            box_width = x1 - x0
            box_height = y1 - y0
            if box_width <= 0 or box_height <= 0:
                continue
            candidates.append(
                VenueVisionCandidate(
                    label="door",
                    confidence=round(min(raw_score, self.maximum_confidence), 4),
                    bounding_box=(
                        round(x0 / width, 4),
                        round(y0 / height, 4),
                        round(box_width / width, 4),
                        round(box_height / height, 4),
                    ),
                    area_fraction=round(box_width * box_height / (width * height), 4),
                )
            )
            if len(candidates) >= 2:
                break
        return candidates
