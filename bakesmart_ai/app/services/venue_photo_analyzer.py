"""Local, model-free venue-photo quality and structure analysis.

This module deliberately reports only pixel-derived facts. It does not claim
that walls, doors, furniture, outlets, or real-world scale were recognised.
Those safety-critical facts must come from customer-confirmed measurements and
the obstacle map until BakeSmart has a reviewed, labelled image dataset.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.schemas.design import (
    PhotoQuality,
    VenuePhotoAnalysis,
    VenuePhotoAnalysisRequest,
)


MAX_PHOTO_BYTES = 8_000_000
MAX_PHOTO_PIXELS = 24_000_000
SUPPORTED_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
}


class VenuePhotoAnalyzer:
    """Extract reproducible image-quality signals without a pretrained model."""

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
                oriented = ImageOps.exif_transpose(source).convert("L")
                width, height = oriented.size
                oriented.thumbnail((512, 512), Image.Resampling.BILINEAR)
                pixels = np.asarray(oriented, dtype=np.float64)
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
        digest = hashlib.sha256(image_bytes).hexdigest()[:20]
        return VenuePhotoAnalysis(
            photo_id=f"venue-photo-{digest}",
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
            observations=observations,
            limitations=[
                "No doors, windows, furniture, outlets, or walkways are automatically confirmed.",
                "Exact scale comes only from customer-confirmed measurements, not photo pixels.",
                "The uploaded photo is analysed in memory and is not persisted by this endpoint.",
            ],
            exact_scale_available=False,
            persisted=False,
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
