"""Local venue-photo quality and synthetic-bootstrap segmentation analysis.

The quality signals are deterministic pixel calculations. Segmentation regions
come from BakeSmart's own randomly initialized synthetic-bootstrap checkpoint.
Neither source confirms safety-critical objects or real-world scale.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.schemas.design import (
    CakePhotoUploadRequest,
    PhotoQuality,
    TemporaryPhotoAsset,
    VenuePhotoAnalysis,
    VenuePhotoAnalysisRequest,
    VenueVisionCandidate,
)
from app.services.photo_artifacts import TemporaryPhotoStore, temporary_photo_store
from training.venue_vision_runtime import VenueVisionRuntime

try:
    from training.real_venue_runtime import RealVenueSegmentationRuntime
except ImportError:  # pragma: no cover - synthetic fallback remains available
    RealVenueSegmentationRuntime = None  # type: ignore[assignment,misc]

try:
    from training.venue_vision_bundle_v6_runtime import VenueVisionBundleV6Runtime
except ImportError:  # pragma: no cover - older/synthetic runtimes remain available
    VenueVisionBundleV6Runtime = None  # type: ignore[assignment,misc]


MAX_PHOTO_BYTES = 8_000_000
MAX_PHOTO_PIXELS = 24_000_000
SUPPORTED_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
}


class VenuePhotoAnalyzer:
    """Extract reproducible image-quality signals without a pretrained model."""

    def __init__(
        self,
        photo_store: TemporaryPhotoStore = temporary_photo_store,
    ) -> None:
        self.photo_store = photo_store
        self.final_vision_runtime = None
        if VenueVisionBundleV6Runtime is not None:
            try:
                self.final_vision_runtime = VenueVisionBundleV6Runtime.load()
            except (
                FileNotFoundError,
                ImportError,
                KeyError,
                TypeError,
                ValueError,
                OSError,
                RuntimeError,
            ):
                self.final_vision_runtime = None
        self.real_vision_runtime = None
        if self.final_vision_runtime is None and RealVenueSegmentationRuntime is not None:
            try:
                self.real_vision_runtime = RealVenueSegmentationRuntime.load()
            except (
                FileNotFoundError,
                ImportError,
                KeyError,
                TypeError,
                ValueError,
                OSError,
            ):
                self.real_vision_runtime = None
        self.vision_runtime: VenueVisionRuntime | None = None
        try:
            self.vision_runtime = VenueVisionRuntime.load()
        except (FileNotFoundError, KeyError, TypeError, ValueError, OSError):
            self.vision_runtime = None

    def analyze(self, request: VenuePhotoAnalysisRequest) -> VenuePhotoAnalysis:
        image_bytes = self._decode(request.image_base64)
        if len(image_bytes) > MAX_PHOTO_BYTES:
            raise ValueError("Venue photo must be 8 MB or smaller.")

        try:
            with Image.open(BytesIO(image_bytes)) as source:
                if source.format != SUPPORTED_FORMATS[request.media_type]:
                    raise ValueError(
                        "Venue photo content does not match its declared media type."
                    )
                width, height = source.size
                if width * height > MAX_PHOTO_PIXELS:
                    raise ValueError("Venue photo exceeds the 24-megapixel limit.")
                oriented_rgb = ImageOps.exif_transpose(source).convert("RGB")
                width, height = oriented_rgb.size
                vision_pixels = None
                if self.final_vision_runtime is None and self.real_vision_runtime is None:
                    vision_size = (
                        self.vision_runtime.image_size if self.vision_runtime else 48
                    )
                    vision_pixels = np.asarray(
                        oriented_rgb.resize(
                            (vision_size, vision_size),
                            Image.Resampling.BILINEAR,
                        ),
                        dtype=np.uint8,
                    )
                grayscale = oriented_rgb.convert("L")
                grayscale.thumbnail((512, 512), Image.Resampling.BILINEAR)
                pixels = np.asarray(grayscale, dtype=np.float64)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(
                "Venue photo is not a readable JPEG or PNG image."
            ) from exc

        if pixels.size == 0:
            raise ValueError("Venue photo contains no readable pixels.")

        brightness = float(np.mean(pixels) / 255.0)
        contrast = float(min(np.std(pixels) / 64.0, 1.0))
        sharpness = self._sharpness(pixels)
        structure_score, structure_row = self._horizontal_structure(pixels)
        orientation = self._orientation(width, height)
        quality = self._quality(
            width,
            height,
            orientation,
            brightness,
            contrast,
            sharpness,
        )
        observations = self._observations(
            width,
            height,
            orientation,
            brightness,
            contrast,
            sharpness,
            structure_score,
            structure_row,
        )
        candidates: list[VenueVisionCandidate] = []
        vision_model_version: str | None = None
        active_model_source: str | None = None
        if self.final_vision_runtime is not None:
            vision_model_version = self.final_vision_runtime.model_version
            candidates = [
                VenueVisionCandidate(
                    label=candidate.label,
                    confidence=candidate.confidence,
                    bounding_box=candidate.bounding_box,
                    area_fraction=candidate.area_fraction,
                    confirmed=False,
                    source="validation_only_v6_bundle",
                )
                for candidate in self.final_vision_runtime.candidates(oriented_rgb)
            ]
            active_model_source = "validation-only v5 room plus v6 Door bundle"
        elif self.real_vision_runtime is not None:
            vision_model_version = self.real_vision_runtime.model_version
            candidates = [
                VenueVisionCandidate(
                    label=candidate.label,
                    confidence=candidate.confidence,
                    bounding_box=candidate.bounding_box,
                    area_fraction=candidate.area_fraction,
                    confirmed=False,
                    source="reviewed_real_six_class_model",
                )
                for candidate in self.real_vision_runtime.candidates(oriented_rgb)
            ]
            active_model_source = "reviewed real-photo six-class model"
        elif self.vision_runtime is not None and vision_pixels is not None:
            vision_model_version = self.vision_runtime.model_version
            candidates = [
                VenueVisionCandidate(
                    label=candidate.label,
                    confidence=candidate.confidence,
                    bounding_box=candidate.bounding_box,
                    area_fraction=candidate.area_fraction,
                    confirmed=False,
                    source="synthetic_bootstrap_model",
                )
                for candidate in self.vision_runtime.candidates(vision_pixels)
            ]
            active_model_source = "synthetic-bootstrap model"
        if active_model_source is not None:
            observations.append(
                f"The {active_model_source} proposed "
                f"{len(candidates)} unconfirmed region candidate(s)."
            )
        digest = hashlib.sha256(image_bytes).hexdigest()[:20]
        photo_id = f"venue-photo-{digest}"
        _, expires_at = self.photo_store.write(photo_id, oriented_rgb)
        return VenuePhotoAnalysis(
            photo_id=photo_id,
            angle=request.angle,
            pixel_width=width,
            pixel_height=height,
            file_size_bytes=len(image_bytes),
            orientation=orientation,
            quality=quality,
            brightness_score=round(brightness, 4),
            contrast_score=round(contrast, 4),
            sharpness_score=round(sharpness, 4),
            horizontal_structure_score=round(structure_score, 4),
            vision_model_version=vision_model_version,
            unconfirmed_candidates=candidates,
            observations=observations,
            limitations=[
                "No doors, windows, furniture, outlets, or walkways are automatically confirmed.",
                (
                    "The validation-only v6 bundle uses v5 for room regions and v6 for "
                    "Door suggestions; Outlet marking remains manual and every candidate "
                    "must be customer-confirmed."
                    if self.final_vision_runtime is not None
                    else (
                        "Vision candidates use the frozen reviewed-real six-class checkpoint; "
                        "Walkway is derived separately from predicted Floor and all confidence "
                        "values remain capped below 0.50."
                        if self.real_vision_runtime is not None
                        else (
                            "Vision candidates come from synthetic training only and are "
                            "capped below 0.50 confidence."
                        )
                    )
                ),
                "Exact scale comes only from customer-confirmed measurements, not photo pixels.",
                "The uploaded photo is stored locally for up to 24 hours only so "
                "BakeSmart can create photo-based concept previews.",
            ],
            exact_scale_available=False,
            persisted=False,
            temporarily_stored=True,
            temporary_storage_expires_at=expires_at,
        )

    def store_cake_photo(
        self,
        request: CakePhotoUploadRequest,
    ) -> TemporaryPhotoAsset:
        image_bytes = self._decode(request.image_base64)
        if len(image_bytes) > MAX_PHOTO_BYTES:
            raise ValueError("Cake photo must be 8 MB or smaller.")
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                if source.format != SUPPORTED_FORMATS[request.media_type]:
                    raise ValueError(
                        "Cake photo content does not match its declared media type."
                    )
                width, height = source.size
                if width * height > MAX_PHOTO_PIXELS:
                    raise ValueError("Cake photo exceeds the 24-megapixel limit.")
                oriented_rgb = ImageOps.exif_transpose(source).convert("RGB")
                width, height = oriented_rgb.size
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Cake photo is not a readable JPEG or PNG image.") from exc
        asset_id = self.photo_store.asset_id("cake", image_bytes)
        _, expires_at = self.photo_store.write(asset_id, oriented_rgb)
        return TemporaryPhotoAsset(
            asset_id=asset_id,
            pixel_width=width,
            pixel_height=height,
            expires_at=expires_at,
            persisted_permanently=False,
        )

    @staticmethod
    def _decode(encoded: str) -> bytes:
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Venue photo is not valid base64 data.") from exc

    @staticmethod
    def _orientation(width: int, height: int) -> str:
        if abs(width - height) <= max(width, height) * 0.05:
            return "square"
        return "landscape" if width > height else "portrait"

    @staticmethod
    def _sharpness(pixels: np.ndarray) -> float:
        if min(pixels.shape) < 3:
            return 0.0
        centre = pixels[1:-1, 1:-1]
        laplacian = (
            -4 * centre
            + pixels[:-2, 1:-1]
            + pixels[2:, 1:-1]
            + pixels[1:-1, :-2]
            + pixels[1:-1, 2:]
        )
        return float(min(np.sqrt(np.var(laplacian)) / 64.0, 1.0))

    @staticmethod
    def _horizontal_structure(pixels: np.ndarray) -> tuple[float, float | None]:
        if pixels.shape[0] < 2:
            return 0.0, None
        row_means = np.mean(pixels, axis=1)
        transitions = np.abs(np.diff(row_means))
        index = int(np.argmax(transitions))
        score = float(min(transitions[index] / 48.0, 1.0))
        row = float((index + 1) / pixels.shape[0])
        return score, row

    @staticmethod
    def _quality(
        width: int,
        height: int,
        orientation: str,
        brightness: float,
        contrast: float,
        sharpness: float,
    ) -> PhotoQuality:
        checks = [
            width >= 1024 and height >= 576,
            orientation == "landscape",
            0.18 <= brightness <= 0.90,
            contrast >= 0.12,
            sharpness >= 0.05,
        ]
        passed = sum(checks)
        if passed >= 5:
            return PhotoQuality.HIGH
        if passed >= 3:
            return PhotoQuality.MEDIUM
        return PhotoQuality.LOW

    @staticmethod
    def _observations(
        width: int,
        height: int,
        orientation: str,
        brightness: float,
        contrast: float,
        sharpness: float,
        structure_score: float,
        structure_row: float | None,
    ) -> list[str]:
        observations = [
            f"The selected file is a {orientation} photo measuring {width} × {height} pixels."
        ]
        if brightness < 0.18:
            observations.append(
                "The photo pixels are very dark; visible details may be missed."
            )
        elif brightness > 0.90:
            observations.append(
                "The photo pixels are very bright; highlights may hide details."
            )
        else:
            observations.append(
                "The overall photo brightness is usable for visual review."
            )
        observations.append(
            "Pixel contrast is usable."
            if contrast >= 0.12
            else "Pixel contrast is low; wall and object boundaries may be unclear."
        )
        observations.append(
            "Edge sharpness is usable."
            if sharpness >= 0.05
            else "Edge sharpness is low; take a steadier photo if possible."
        )
        if structure_score >= 0.25 and structure_row is not None:
            observations.append(
                "A strong horizontal pixel transition appears near "
                f"{round(structure_row * 100)}% of the image height; it is only a "
                "structural cue and is not treated as a confirmed wall or floor boundary."
            )
        return observations


venue_photo_analyzer = VenuePhotoAnalyzer()
