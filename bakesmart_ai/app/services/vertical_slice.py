"""Professional review slice for Birthday, Wedding, and South Asian Mehndi.

This module never stretches a production asset. It only places true-size modules
and reports whether the first three celebration slices are structurally ready for
visual review. Customer rendering remains blocked until production approval.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.assets import (
    VerticalSliceAssetState,
    VerticalSliceCelebration,
    VerticalSliceCelebrationState,
    VerticalSliceCompositionRequest,
    VerticalSliceCompositionResponse,
    VerticalSlicePlacement,
    VerticalSliceSummaryResponse,
)
from app.services.production_assets import (
    ProductionAssetRegistry,
    inspect_glb_bytes,
    production_asset_registry,
)
from app.services.vertical_slice_assets import generate_review_asset_map


@dataclass(frozen=True)
class _SliceAsset:
    asset_id: str
    role: str


SLICE_ASSETS: dict[VerticalSliceCelebration, tuple[_SliceAsset, ...]] = {
    "birthday": (
        _SliceAsset("prod-backdrop-chiara-panels", "backdrop"),
        _SliceAsset("prod-floor-balloon-clusters", "support"),
        _SliceAsset("prod-lighting-curtain", "lighting"),
        _SliceAsset("prod-sign-foamboard-welcome", "signage"),
    ),
    "wedding": (
        _SliceAsset("prod-backdrop-floral-arch", "backdrop"),
        _SliceAsset("prod-floor-floral-pedestal-pair", "support"),
        _SliceAsset("prod-table-low-floral", "table"),
        _SliceAsset("prod-lighting-led-candles", "lighting"),
    ),
    "south_asian_mehndi": (
        _SliceAsset("prod-backdrop-south-asian-stage", "backdrop"),
        _SliceAsset("prod-floor-marigold-clusters", "support"),
        _SliceAsset("prod-table-mehndi-textile", "table"),
        _SliceAsset("prod-lighting-festoon", "lighting"),
    ),
}

DISPLAY_NAMES: dict[VerticalSliceCelebration, str] = {
    "birthday": "Birthday",
    "wedding": "Wedding",
    "south_asian_mehndi": "South Asian Mehndi",
}


class VerticalSliceService:
    """Track and compose the first true-size professional asset slices."""

    _limitations = [
        "The committed v1 slice GLBs are BakeSmart-created low-poly geometry prototypes for structural and scale review; they are not artist-approved photorealistic assets.",
        "Prototype GLBs use PBR material factors and vertex colour, but the current customer viewer still uses BakeSmart's procedural vertex-colour renderer.",
        "The slice endpoints are review-only until each asset passes geometry, material, LOD, rights, and production approval.",
        "Composition uses true dimensions only; no fixed structural asset is stretched to fill a larger venue.",
        "Final collision and circulation approval still comes from the confirmed metre-based room constraint engine.",
    ]

    def __init__(
        self,
        registry: ProductionAssetRegistry = production_asset_registry,
    ) -> None:
        self.registry = registry
        self.review_assets = generate_review_asset_map()

    def summary(self) -> VerticalSliceSummaryResponse:
        celebrations = [
            self._celebration_state(celebration)
            for celebration in ("birthday", "wedding", "south_asian_mehndi")
        ]
        return VerticalSliceSummaryResponse(
            geometry_review_assets_present=all(
                item.geometry_slice_complete for item in celebrations
            ),
            customer_runtime_ready=all(
                item.customer_slice_ready for item in celebrations
            ),
            celebrations=celebrations,
            limitations=list(self._limitations),
        )

    def _celebration_state(
        self,
        celebration: VerticalSliceCelebration,
    ) -> VerticalSliceCelebrationState:
        states: list[VerticalSliceAssetState] = []
        for slice_asset in SLICE_ASSETS[celebration]:
            record = self.registry.by_asset_id[slice_asset.asset_id]
            data = self.review_assets.get(record.asset_id)
            present = data is not None
            errors: list[str] = []
            if data is not None:
                _, errors, _, _ = inspect_glb_bytes(data, record)
            structurally_valid = present and not errors
            states.append(
                VerticalSliceAssetState(
                    asset_id=record.asset_id,
                    catalog_id=record.catalog_id,
                    role=slice_asset.role,
                    glb_present=present,
                    structurally_valid=structurally_valid,
                    production_status=record.production_status,
                    customer_renderable=self.registry.is_renderable_catalog_item(
                        record.catalog_id
                    ),
                    review_glb_url=(
                        f"/api/v1/assets/3d/review/{record.asset_id}.glb"
                        if structurally_valid
                        else None
                    ),
                )
            )

        required = len(states)
        present_count = sum(item.glb_present for item in states)
        structural_count = sum(item.structurally_valid for item in states)
        ready_count = sum(item.customer_renderable for item in states)
        blockers: list[str] = []
        if present_count < required:
            blockers.append(
                f"{required - present_count} required slice GLB(s) are still missing."
            )
        if structural_count < present_count:
            blockers.append(
                f"{present_count - structural_count} present GLB(s) failed structural validation."
            )
        if ready_count < required:
            blockers.append(
                "Geometry/material review and explicit production approval are still required before these assets can replace the customer procedural fallback."
            )
        return VerticalSliceCelebrationState(
            celebration=celebration,
            display_name=DISPLAY_NAMES[celebration],
            required_asset_count=required,
            present_glb_count=present_count,
            structurally_valid_count=structural_count,
            production_ready_count=ready_count,
            geometry_slice_complete=structural_count == required,
            customer_slice_ready=ready_count == required,
            assets=states,
            blockers=blockers,
        )

    def review_glb(self, asset_id: str) -> bytes:
        """Return one structurally valid generated review GLB."""

        record = self.registry.by_asset_id.get(asset_id)
        if record is None:
            raise KeyError(asset_id)
        data = self.review_assets.get(asset_id)
        if data is None:
            raise FileNotFoundError(asset_id)
        _, errors, _, _ = inspect_glb_bytes(data, record)
        if errors:
            raise ValueError("; ".join(errors))
        return data

    def compose(
        self,
        request: VerticalSliceCompositionRequest,
    ) -> VerticalSliceCompositionResponse:
        usable = request.usable_focal_width_m
        requested = request.target_visual_width_m
        target = min(usable, requested)
        notes: list[str] = []
        if requested > usable:
            notes.append(
                f"Requested visual width {requested:.2f} m exceeds the usable focal width {usable:.2f} m; the review plan is capped to the confirmed usable span."
            )

        if request.celebration == "birthday":
            placements, achieved, status, more = self._birthday(
                usable,
                target,
                request.include_lighting,
            )
        elif request.celebration == "wedding":
            placements, achieved, status, more = self._wedding(
                usable,
                target,
                request.include_lighting,
            )
        else:
            placements, achieved, status, more = self._mehndi(
                usable,
                target,
                request.include_lighting,
            )
        notes.extend(more)
        if status == "fits" and requested > usable:
            status = "partial"
        return VerticalSliceCompositionResponse(
            celebration=request.celebration,
            status=status,
            usable_focal_width_m=usable,
            requested_visual_width_m=requested,
            achieved_visual_width_m=round(achieved, 3),
            placements=placements,
            notes=list(dict.fromkeys(notes)),
        )

    def _placement(
        self,
        asset_id: str,
        role: str,
        index: int,
        x_center_m: float,
        depth_m: float,
        base_height_m: float = 0.0,
    ) -> VerticalSlicePlacement:
        record = self.registry.by_asset_id[asset_id]
        return VerticalSlicePlacement(
            asset_id=record.asset_id,
            catalog_id=record.catalog_id,
            role=role,
            instance_index=index,
            x_center_m=round(x_center_m, 3),
            depth_from_focal_wall_m=round(depth_m, 3),
            base_height_m=round(base_height_m, 3),
            uniform_scale=1.0,
            true_width_m=record.dimensions.width_m,
            true_depth_m=record.dimensions.depth_m or 0.01,
            true_height_m=record.dimensions.height_m,
        )

    @staticmethod
    def _visual_span(placements: list[VerticalSlicePlacement]) -> float:
        visual = [
            item
            for item in placements
            if item.role in {"backdrop", "support", "lighting", "signage"}
        ]
        if not visual:
            return 0.0
        left = min(item.x_center_m - item.true_width_m / 2 for item in visual)
        right = max(item.x_center_m + item.true_width_m / 2 for item in visual)
        return max(0.0, right - left)

    def _add_symmetric_supports(
        self,
        placements: list[VerticalSlicePlacement],
        *,
        asset_id: str,
        role: str,
        center_width_m: float,
        usable_width_m: float,
        target_width_m: float,
        depth_m: float,
        gap_m: float = 0.10,
        max_pairs: int = 4,
    ) -> None:
        record = self.registry.by_asset_id[asset_id]
        module_width = record.dimensions.width_m
        current_half = center_width_m / 2
        limit_half = min(usable_width_m, target_width_m) / 2
        pair = 0
        while pair < max_pairs:
            center_offset = current_half + gap_m + module_width / 2
            if center_offset + module_width / 2 > limit_half + 1e-6:
                break
            pair += 1
            placements.append(
                self._placement(
                    asset_id,
                    role,
                    pair * 2 - 1,
                    -center_offset,
                    depth_m,
                )
            )
            placements.append(
                self._placement(
                    asset_id,
                    role,
                    pair * 2,
                    center_offset,
                    depth_m,
                )
            )
            current_half = center_offset + module_width / 2

    def _birthday(
        self,
        usable: float,
        target: float,
        include_lighting: bool,
    ) -> tuple[list[VerticalSlicePlacement], float, str, list[str]]:
        backdrop = self.registry.by_asset_id["prod-backdrop-chiara-panels"]
        if usable + 1e-6 < backdrop.dimensions.width_m:
            return (
                [],
                0.0,
                "does_not_fit",
                [
                    f"The true-size 2.60 m Chiara backdrop cannot fit a {usable:.2f} m usable focal span. Select a smaller approved backdrop instead of shrinking it."
                ],
            )
        placements = [
            self._placement(
                "prod-backdrop-chiara-panels",
                "backdrop",
                1,
                0.0,
                (backdrop.dimensions.depth_m or 0.65) / 2,
            )
        ]
        self._add_symmetric_supports(
            placements,
            asset_id="prod-floor-balloon-clusters",
            role="support",
            center_width_m=backdrop.dimensions.width_m,
            usable_width_m=usable,
            target_width_m=target,
            depth_m=0.75,
            max_pairs=3,
        )
        if include_lighting and usable >= 3.0 and target >= 2.8:
            placements.append(
                self._placement(
                    "prod-lighting-curtain",
                    "lighting",
                    1,
                    0.0,
                    0.05,
                )
            )
        sign = self.registry.by_asset_id["prod-sign-foamboard-welcome"]
        current = self._visual_span(placements)
        if usable >= current + sign.dimensions.width_m + 0.15:
            x = min(
                usable / 2 - sign.dimensions.width_m / 2,
                current / 2 + 0.10 + sign.dimensions.width_m / 2,
            )
            placements.append(
                self._placement(
                    "prod-sign-foamboard-welcome",
                    "signage",
                    1,
                    x,
                    1.0,
                )
            )
        achieved = min(usable, self._visual_span(placements))
        status = "fits" if achieved + 0.10 >= target else "partial"
        return (
            placements,
            achieved,
            status,
            [
                "Birthday slice uses a true-size 2.60 m three-panel backdrop and adds separate balloon/sign/lighting modules instead of scaling the backdrop.",
            ],
        )

    def _wedding(
        self,
        usable: float,
        target: float,
        include_lighting: bool,
    ) -> tuple[list[VerticalSlicePlacement], float, str, list[str]]:
        backdrop = self.registry.by_asset_id["prod-backdrop-floral-arch"]
        if usable + 1e-6 < backdrop.dimensions.width_m:
            return (
                [],
                0.0,
                "does_not_fit",
                [
                    f"The true-size 2.80 m floral arch cannot fit a {usable:.2f} m usable focal span. Do not shrink the ceremony structure."
                ],
            )
        placements = [
            self._placement(
                "prod-backdrop-floral-arch",
                "backdrop",
                1,
                0.0,
                (backdrop.dimensions.depth_m or 0.9) / 2,
            )
        ]
        self._add_symmetric_supports(
            placements,
            asset_id="prod-floor-floral-pedestal-pair",
            role="support",
            center_width_m=backdrop.dimensions.width_m,
            usable_width_m=usable,
            target_width_m=target,
            depth_m=0.95,
            max_pairs=3,
        )
        placements.append(
            self._placement(
                "prod-table-low-floral",
                "table",
                1,
                0.0,
                1.15,
                0.90,
            )
        )
        if include_lighting:
            for index, x in enumerate((-0.30, 0.30), start=1):
                placements.append(
                    self._placement(
                        "prod-lighting-led-candles",
                        "lighting",
                        index,
                        x,
                        1.15,
                        0.90,
                    )
                )
        achieved = min(usable, self._visual_span(placements))
        status = "fits" if achieved + 0.10 >= target else "partial"
        return (
            placements,
            achieved,
            status,
            [
                "Wedding slice expands visual width with separate floral pedestal modules while the 2.80 m ceremony arch remains at true size.",
                "Tabletop floral/candle placements are review anchors only and require the final cake-table dimensions before hard collision approval.",
            ],
        )

    def _mehndi(
        self,
        usable: float,
        target: float,
        include_lighting: bool,
    ) -> tuple[list[VerticalSlicePlacement], float, str, list[str]]:
        backdrop = self.registry.by_asset_id["prod-backdrop-south-asian-stage"]
        if usable + 1e-6 < backdrop.dimensions.width_m:
            return (
                [],
                0.0,
                "does_not_fit",
                [
                    f"The true-size 5.00 m South Asian stage cannot fit a {usable:.2f} m usable focal span. BakeSmart must select a smaller Mehndi module set rather than shrinking this stage."
                ],
            )
        placements = [
            self._placement(
                "prod-backdrop-south-asian-stage",
                "backdrop",
                1,
                0.0,
                (backdrop.dimensions.depth_m or 1.8) / 2,
            )
        ]
        self._add_symmetric_supports(
            placements,
            asset_id="prod-floor-marigold-clusters",
            role="support",
            center_width_m=backdrop.dimensions.width_m,
            usable_width_m=usable,
            target_width_m=target,
            depth_m=1.45,
            max_pairs=4,
        )
        placements.append(
            self._placement(
                "prod-table-mehndi-textile",
                "table",
                1,
                0.0,
                1.55,
                0.0,
            )
        )
        if include_lighting:
            festoon = self.registry.by_asset_id["prod-lighting-festoon"]
            if usable + 1e-6 >= festoon.dimensions.width_m:
                placements.append(
                    self._placement(
                        "prod-lighting-festoon",
                        "lighting",
                        1,
                        0.0,
                        0.4,
                        2.7,
                    )
                )
            else:
                lighting_note = (
                    "The 10.00 m festoon module is intentionally omitted because it does not fit the confirmed focal span at true size."
                )
                achieved = min(usable, self._visual_span(placements))
                status = "fits" if achieved + 0.10 >= target else "partial"
                return (
                    placements,
                    achieved,
                    status,
                    [
                        "Mehndi slice keeps the 5.00 m layered stage at true size and uses separate marigold modules for additional visual spread.",
                        lighting_note,
                    ],
                )
        achieved = min(usable, self._visual_span(placements))
        status = "fits" if achieved + 0.10 >= target else "partial"
        return (
            placements,
            achieved,
            status,
            [
                "Mehndi slice keeps the 5.00 m layered stage at true size and uses separate marigold modules for additional visual spread.",
            ],
        )


vertical_slice_service = VerticalSliceService()
