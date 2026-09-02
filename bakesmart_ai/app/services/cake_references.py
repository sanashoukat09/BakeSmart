"""Measured reference profiles for BakeSmart's configurable cake geometry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "data" / "cake_references_v1" / "profiles.json"


@dataclass(frozen=True)
class CakeReferenceProfile:
    profile_id: str
    source_id: str
    catalog_tokens: tuple[str, ...]
    measured_height_to_width: float
    tier_taper: float
    frosting_roughness: float
    piping_radius_fraction: float
    topper_cluster_radius_fraction: float
    accent_style: str


class CakeReferenceLibrary:
    def __init__(self, path: Path = PROFILE_PATH):
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.minimum_tier_scale = float(payload["rules"]["minimum_tier_scale"])
        self.external_source_ids = tuple(payload["available_external_reference_source_ids"])
        self.profiles = tuple(
            CakeReferenceProfile(
                profile_id=row["profile_id"],
                source_id=row["source_id"],
                catalog_tokens=tuple(row["catalog_tokens"]),
                measured_height_to_width=float(row["measured_height_to_width"]),
                tier_taper=float(row["tier_taper"]),
                frosting_roughness=float(row["frosting_roughness"]),
                piping_radius_fraction=float(row["piping_radius_fraction"]),
                topper_cluster_radius_fraction=float(row["topper_cluster_radius_fraction"]),
                accent_style=row["accent_style"],
            )
            for row in payload["profiles"]
        )
        by_id = {profile.profile_id: profile for profile in self.profiles}
        self.default = by_id[payload["default_profile_id"]]
        if len(by_id) != len(self.profiles):
            raise ValueError("cake reference profile ids must be unique")
        if not all(0 < profile.tier_taper < 1 for profile in self.profiles):
            raise ValueError("cake reference tier taper must be between zero and one")
        if not 0 < self.minimum_tier_scale <= 1:
            raise ValueError("minimum cake tier scale must be between zero and one")
        profile_sources = {profile.source_id for profile in self.profiles}
        if not set(self.external_source_ids) <= profile_sources:
            raise ValueError("every external cake reference must be assigned to a profile")

    def select(self, catalog_id: str | None) -> CakeReferenceProfile:
        normalized = (catalog_id or "").lower().replace("_", "-")
        scored = [
            (
                sum(token in normalized for token in profile.catalog_tokens),
                profile.profile_id,
                profile,
            )
            for profile in self.profiles
        ]
        score, _profile_id, profile = max(scored)
        return profile if score > 0 else self.default


cake_reference_library = CakeReferenceLibrary()
