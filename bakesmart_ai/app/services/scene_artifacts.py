"""Safe local persistence for generated BakeSmart scene files."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


DESIGN_ID_PATTERN = re.compile(r"^design-[0-9a-f]{20}$")
DEFAULT_SCENE_DIR = Path(__file__).resolve().parents[2] / "runtime" / "scenes"


class SceneArtifactStore:
    def __init__(self, scene_dir: Path = DEFAULT_SCENE_DIR) -> None:
        self.scene_dir = scene_dir.resolve()

    @staticmethod
    def validate_design_id(design_id: str) -> str:
        if not DESIGN_ID_PATTERN.fullmatch(design_id):
            raise ValueError("invalid BakeSmart design ID")
        return design_id

    def path_for(self, design_id: str) -> Path:
        validated = self.validate_design_id(design_id)
        return self.scene_dir / f"{validated}.glb"

    def manifest_path_for(self, design_id: str) -> Path:
        validated = self.validate_design_id(design_id)
        return self.scene_dir / f"{validated}.modules.json"

    def write(self, design_id: str, data: bytes) -> Path:
        if not data.startswith(b"glTF"):
            raise ValueError("scene artifact is not a GLB file")
        path = self.path_for(design_id)
        self.scene_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=self.scene_dir,
            prefix=f".{design_id}-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            temporary = Path(handle.name)
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def existing_path(self, design_id: str) -> Path | None:
        path = self.path_for(design_id)
        return path if path.is_file() else None

    def write_manifest(self, design_id: str, payload: dict[str, Any]) -> Path:
        if payload.get("design_id") != self.validate_design_id(design_id):
            raise ValueError("scene manifest design ID does not match its artifact ID")
        path = self.manifest_path_for(design_id)
        self.scene_dir.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with tempfile.NamedTemporaryFile(
            dir=self.scene_dir,
            prefix=f".{design_id}-modules-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(encoded)
            temporary = Path(handle.name)
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def existing_manifest_path(self, design_id: str) -> Path | None:
        path = self.manifest_path_for(design_id)
        return path if path.is_file() else None
