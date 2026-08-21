"""Derive a separate visual walkway mask from BakeSmart Floor pixels.

Walkway is not a semantic class. BakeSmart keeps Wall/Floor/Door/Window/
Furniture/Outlet in the main semantic mask and stores Walkway separately as a
binary mask. This preserves all Floor pixels for semantic-model training while
still giving placement logic a visual usable-floor candidate.

Legacy class-6 pixels are accepted as input and normalized back to Floor in
memory. They are never required in new semantic masks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


FLOOR_ID = 1
LEGACY_WALKWAY_ID = 6
UNLABELLED_ID = 255
SEMANTIC_IDS = frozenset(range(6))
VALID_INPUT_IDS = SEMANTIC_IDS | {LEGACY_WALKWAY_ID, UNLABELLED_ID}
DEFAULT_CLEARANCE_FRACTION = 0.015
MAX_CLEARANCE_PIXELS = 24
MIN_WALKWAY_COMPONENT_FRACTION = 0.0015


@dataclass(frozen=True)
class WalkwayGenerationResult:
    semantic_labels: np.ndarray
    walkway_mask: np.ndarray
    clearance_pixels: int
    floor_pixels_before: int
    walkway_pixels: int
    walkway_components: int
    walkway_fraction_of_floor: float

    @property
    def labels(self) -> np.ndarray:
        """Backward-compatible alias returning semantic labels only."""

        return self.semantic_labels


def derive_walkway_candidate(
    labels: np.ndarray,
    *,
    clearance_pixels: int | None = None,
    clearance_fraction: float = DEFAULT_CLEARANCE_FRACTION,
) -> WalkwayGenerationResult:
    """Return normalized semantic labels plus a separate 0/1 walkway mask.

    New semantic outputs contain only IDs 0-5 and 255. Legacy class-6 pixels
    are restored to Floor before the walkway is regenerated.
    """

    source = np.asarray(labels)
    if source.ndim != 2:
        raise ValueError("walkway generation requires a single-channel label mask")
    if source.size == 0:
        raise ValueError("walkway generation requires a non-empty label mask")
    unique_ids = {int(value) for value in np.unique(source)}
    invalid = unique_ids - VALID_INPUT_IDS
    if invalid:
        raise ValueError(f"walkway generation received invalid label IDs: {sorted(invalid)}")
    if not 0 < clearance_fraction <= 0.20:
        raise ValueError("clearance_fraction must be greater than 0 and at most 0.20")

    height, width = source.shape
    if clearance_pixels is None:
        clearance_pixels = max(1, round(min(height, width) * clearance_fraction))
        clearance_pixels = min(clearance_pixels, MAX_CLEARANCE_PIXELS)
    if clearance_pixels < 0:
        raise ValueError("clearance_pixels must be >= 0")

    semantic = source.astype(np.uint8, copy=True)
    semantic[semantic == LEGACY_WALKWAY_ID] = FLOOR_ID
    floor = semantic == FLOOR_ID
    floor_pixels = int(np.count_nonzero(floor))
    if floor_pixels == 0:
        return WalkwayGenerationResult(
            semantic_labels=semantic,
            walkway_mask=np.zeros_like(semantic, dtype=np.uint8),
            clearance_pixels=int(clearance_pixels),
            floor_pixels_before=0,
            walkway_pixels=0,
            walkway_components=0,
            walkway_fraction_of_floor=0.0,
        )

    interior = _erode_eight_connected(floor, int(clearance_pixels))
    minimum_component_pixels = max(
        9,
        round(semantic.size * MIN_WALKWAY_COMPONENT_FRACTION),
    )
    interior, component_count = _keep_large_components(
        interior,
        minimum_pixels=minimum_component_pixels,
    )
    walkway_mask = interior.astype(np.uint8)
    walkway_pixels = int(np.count_nonzero(walkway_mask))
    return WalkwayGenerationResult(
        semantic_labels=semantic,
        walkway_mask=walkway_mask,
        clearance_pixels=int(clearance_pixels),
        floor_pixels_before=floor_pixels,
        walkway_pixels=walkway_pixels,
        walkway_components=component_count,
        walkway_fraction_of_floor=round(walkway_pixels / max(floor_pixels, 1), 6),
    )


def _erode_eight_connected(mask: np.ndarray, iterations: int) -> np.ndarray:
    current = mask.astype(bool, copy=True)
    if iterations == 0:
        return current
    height, width = current.shape
    for _ in range(iterations):
        padded = np.pad(current, 1, mode="constant", constant_values=False)
        eroded = np.ones((height, width), dtype=bool)
        for row_offset in range(3):
            for column_offset in range(3):
                eroded &= padded[
                    row_offset : row_offset + height,
                    column_offset : column_offset + width,
                ]
        current = eroded
        if not np.any(current):
            break
    return current


def _keep_large_components(
    mask: np.ndarray,
    *,
    minimum_pixels: int,
) -> tuple[np.ndarray, int]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    kept = np.zeros_like(mask, dtype=bool)
    kept_count = 0
    for row in range(height):
        for column in range(width):
            if not mask[row, column] or visited[row, column]:
                continue
            stack = [(row, column)]
            visited[row, column] = True
            component: list[tuple[int, int]] = []
            while stack:
                current_row, current_column = stack.pop()
                component.append((current_row, current_column))
                for next_row, next_column in (
                    (current_row - 1, current_column),
                    (current_row + 1, current_column),
                    (current_row, current_column - 1),
                    (current_row, current_column + 1),
                ):
                    if (
                        0 <= next_row < height
                        and 0 <= next_column < width
                        and mask[next_row, next_column]
                        and not visited[next_row, next_column]
                    ):
                        visited[next_row, next_column] = True
                        stack.append((next_row, next_column))
            if len(component) < minimum_pixels:
                continue
            rows = np.fromiter((point[0] for point in component), dtype=np.int64)
            columns = np.fromiter((point[1] for point in component), dtype=np.int64)
            kept[rows, columns] = True
            kept_count += 1
    return kept, kept_count
