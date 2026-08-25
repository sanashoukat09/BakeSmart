"""Temporary, path-safe storage for customer photos and concept previews."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image


PHOTO_ID_PATTERN = re.compile(r"^(?:venue|cake)-photo-[0-9a-f]{20}$")
PREVIEW_ID_PATTERN = re.compile(
    r"^(design-[0-9a-f]{20})-(essential|balanced|statement)$"
)
RUNTIME_DIR = Path(__file__).resolve().parents[2] / "runtime"
DEFAULT_PHOTO_DIR = RUNTIME_DIR / "customer_photos"
DEFAULT_PREVIEW_DIR = RUNTIME_DIR / "photo_previews"
DEFAULT_TTL_HOURS = 24
MAX_STORED_EDGE = 1600


class TemporaryPhotoStore:
    def __init__(
        self,
        photo_dir: Path = DEFAULT_PHOTO_DIR,
        *,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        self.photo_dir = photo_dir.resolve()
        self.ttl = timedelta(hours=ttl_hours)

    @staticmethod
    def asset_id(prefix: str, image_bytes: bytes) -> str:
        if prefix not in {"venue", "cake"}:
            raise ValueError("invalid temporary photo prefix")
        digest = hashlib.sha256(image_bytes).hexdigest()[:20]
        return f"{prefix}-photo-{digest}"

    @staticmethod
    def validate_asset_id(asset_id: str) -> str:
        if not PHOTO_ID_PATTERN.fullmatch(asset_id):
            raise ValueError("invalid temporary photo ID")
        return asset_id

    def path_for(self, asset_id: str) -> Path:
        return self.photo_dir / f"{self.validate_asset_id(asset_id)}.jpg"

    def write(self, asset_id: str, image: Image.Image) -> tuple[Path, datetime]:
        self.cleanup_expired()
        path = self.path_for(asset_id)
        self.photo_dir.mkdir(parents=True, exist_ok=True)
        stored = image.convert("RGB")
        stored.thumbnail((MAX_STORED_EDGE, MAX_STORED_EDGE), Image.Resampling.LANCZOS)
        with tempfile.NamedTemporaryFile(
            dir=self.photo_dir,
            prefix=f".{asset_id}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        try:
            stored.save(temporary, format="JPEG", quality=88, optimize=True)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path, datetime.now(timezone.utc) + self.ttl

    def existing_path(self, asset_id: str) -> Path | None:
        self.cleanup_expired()
        path = self.path_for(asset_id)
        return path if path.is_file() else None

    def cleanup_expired(self) -> int:
        if not self.photo_dir.is_dir():
            return 0
        cutoff = time.time() - self.ttl.total_seconds()
        removed = 0
        for path in self.photo_dir.glob("*.jpg"):
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed


class PhotoPreviewStore:
    def __init__(
        self,
        preview_dir: Path = DEFAULT_PREVIEW_DIR,
        *,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        self.preview_dir = preview_dir.resolve()
        self.ttl = timedelta(hours=ttl_hours)

    @staticmethod
    def validate_preview_id(preview_id: str) -> str:
        if not PREVIEW_ID_PATTERN.fullmatch(preview_id):
            raise ValueError("invalid concept preview ID")
        return preview_id

    def path_for(self, preview_id: str) -> Path:
        return self.preview_dir / f"{self.validate_preview_id(preview_id)}.png"

    def write(self, preview_id: str, image: Image.Image) -> Path:
        self.cleanup_expired()
        path = self.path_for(preview_id)
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=self.preview_dir,
            prefix=f".{preview_id}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        try:
            image.convert("RGB").save(temporary, format="PNG", optimize=True)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def existing_path(self, preview_id: str) -> Path | None:
        self.cleanup_expired()
        path = self.path_for(preview_id)
        return path if path.is_file() else None

    def cleanup_expired(self) -> int:
        if not self.preview_dir.is_dir():
            return 0
        cutoff = time.time() - self.ttl.total_seconds()
        removed = 0
        for path in self.preview_dir.glob("*.png"):
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed


temporary_photo_store = TemporaryPhotoStore()
photo_preview_store = PhotoPreviewStore()
