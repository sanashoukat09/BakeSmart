"""Fast local annotation helpers for the BakeSmart venue labeller.

Smart Object uses OpenCV GrabCut with a user-provided rectangle. It is an
annotation aid only: the human annotator still reviews the resulting region.
No pretrained model, cloud API or external annotation platform is used.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from training.annotation_workspace import AnnotationWorkspace


@dataclass(frozen=True)
class SmartObjectResult:
    png_bytes: bytes
    selected_pixels: int
    rectangle: tuple[int, int, int, int]


class SmartAnnotationService:
    """Generate edge-aware object selections from a rough rectangle."""

    def __init__(self, iterations: int = 5) -> None:
        if not 1 <= iterations <= 12:
            raise ValueError("GrabCut iterations must be between 1 and 12")
        self.iterations = iterations

    def smart_object(
        self,
        *,
        workspace: AnnotationWorkspace,
        dataset_key: str,
        scene_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> SmartObjectResult:
        try:
            import cv2
        except ImportError as exc:
            raise ValueError(
                "Smart Object requires OpenCV. Run: pip install -r requirements.txt"
            ) from exc

        image_path = workspace.image_path(dataset_key, scene_id)
        with Image.open(image_path) as source:
            rgb_image = ImageOps.exif_transpose(source).convert("RGB")
            image = np.asarray(rgb_image, dtype=np.uint8)
        image_height, image_width = image.shape[:2]
        rectangle = self._normalize_rectangle(
            x=x,
            y=y,
            width=width,
            height=height,
            image_width=image_width,
            image_height=image_height,
        )
        left, top, rect_width, rect_height = rectangle

        bgr = image[..., ::-1].copy()
        grabcut_mask = np.full((image_height, image_width), cv2.GC_BGD, dtype=np.uint8)
        background_model = np.zeros((1, 65), dtype=np.float64)
        foreground_model = np.zeros((1, 65), dtype=np.float64)
        cv2.grabCut(
            bgr,
            grabcut_mask,
            rectangle,
            background_model,
            foreground_model,
            self.iterations,
            cv2.GC_INIT_WITH_RECT,
        )
        selected = np.isin(grabcut_mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.uint8)

        # Keep only connected foreground touching the central part of the user's
        # rectangle. This removes unrelated patches GrabCut can occasionally
        # include elsewhere in the image.
        centre_mask = np.zeros_like(selected)
        inset_x = max(1, round(rect_width * 0.25))
        inset_y = max(1, round(rect_height * 0.25))
        centre_mask[
            top + inset_y : top + rect_height - inset_y,
            left + inset_x : left + rect_width - inset_x,
        ] = 1
        selected = self._keep_components_touching_seed(selected, centre_mask)

        if not np.any(selected):
            # A completely empty result is not useful. Fall back to the rough
            # rectangle so the user can still correct it quickly.
            selected[top : top + rect_height, left : left + rect_width] = 1

        output = io.BytesIO()
        Image.fromarray((selected * 255).astype(np.uint8), mode="L").save(
            output,
            format="PNG",
        )
        return SmartObjectResult(
            png_bytes=output.getvalue(),
            selected_pixels=int(np.count_nonzero(selected)),
            rectangle=rectangle,
        )

    @staticmethod
    def _normalize_rectangle(
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        image_width: int,
        image_height: int,
    ) -> tuple[int, int, int, int]:
        left = max(0, min(int(x), image_width - 1))
        top = max(0, min(int(y), image_height - 1))
        right = max(left + 1, min(int(x + width), image_width))
        bottom = max(top + 1, min(int(y + height), image_height))
        rect_width = right - left
        rect_height = bottom - top
        if rect_width < 5 or rect_height < 5:
            raise ValueError("Smart Object rectangle must be at least 5×5 pixels")
        if rect_width >= image_width - 1 or rect_height >= image_height - 1:
            raise ValueError("Smart Object box must stay inside the image with some background visible")
        return left, top, rect_width, rect_height

    @staticmethod
    def _keep_components_touching_seed(
        selected: np.ndarray,
        seed: np.ndarray,
    ) -> np.ndarray:
        height, width = selected.shape
        visited = np.zeros_like(selected, dtype=bool)
        kept = np.zeros_like(selected, dtype=np.uint8)
        for row in range(height):
            for column in range(width):
                if not selected[row, column] or visited[row, column]:
                    continue
                stack = [(row, column)]
                visited[row, column] = True
                component: list[tuple[int, int]] = []
                touches_seed = False
                while stack:
                    current_row, current_column = stack.pop()
                    component.append((current_row, current_column))
                    touches_seed = touches_seed or bool(seed[current_row, current_column])
                    for next_row, next_column in (
                        (current_row - 1, current_column),
                        (current_row + 1, current_column),
                        (current_row, current_column - 1),
                        (current_row, current_column + 1),
                    ):
                        if (
                            0 <= next_row < height
                            and 0 <= next_column < width
                            and selected[next_row, next_column]
                            and not visited[next_row, next_column]
                        ):
                            visited[next_row, next_column] = True
                            stack.append((next_row, next_column))
                if touches_seed:
                    rows = np.fromiter((point[0] for point in component), dtype=np.int64)
                    columns = np.fromiter((point[1] for point in component), dtype=np.int64)
                    kept[rows, columns] = 1
        return kept
