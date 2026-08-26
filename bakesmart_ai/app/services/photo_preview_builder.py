"""Compose Stage 4 catalogue cut-outs over the customer's real venue photo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.schemas.design import DecorRecommendation, DesignRequest


CANVAS_SIZE = (1280, 720)
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "real_decor"
PACKAGE_SCALE = {"essential": 0.86, "balanced": 1.0, "statement": 1.1}
ASSET_FILES = {
    "backdrop": "backdrop.webp",
    "floor-arrangement": "floor-arrangement.webp",
    "lighting": "lighting.webp",
    "table-setting": "table-setting.webp",
    "signage": "signage.webp",
}


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = (
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf"]
        if bold
        else ["DejaVuSans.ttf", "Arial.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class PreviewAssetStore:
    """Load and validate the original transparent Stage 4 cut-outs."""

    def __init__(self, asset_dir: Path = ASSET_DIR) -> None:
        self.asset_dir = asset_dir

    def load(self, category: str) -> Image.Image | None:
        filename = ASSET_FILES.get(category)
        if filename is None:
            return None
        path = self.asset_dir / filename
        if not path.is_file():
            return None
        with Image.open(path) as source:
            image = source.convert("RGBA")
        if image.getchannel("A").getextrema()[0] == 255:
            raise ValueError(f"Stage 4 asset '{filename}' has no transparency")
        return image


class PhotoPreviewBuilder:
    """Build a photo-grounded concept without claiming photometric AR accuracy."""

    def __init__(self, asset_store: PreviewAssetStore | None = None) -> None:
        self.asset_store = asset_store or PreviewAssetStore()

    def build(
        self,
        *,
        venue_path: Path,
        cake_path: Path,
        request: DesignRequest,
        package_id: str,
        package_name: str,
        decorations: list[DecorRecommendation],
        palette_hex: str,
        decoration_cost_pkr: int,
    ) -> Image.Image:
        if package_id not in PACKAGE_SCALE:
            raise ValueError("unknown design package")
        del palette_hex  # Real cut-outs retain natural material colours.
        with Image.open(venue_path) as venue_source:
            canvas = ImageOps.fit(
                venue_source.convert("RGB"),
                CANVAS_SIZE,
                method=Image.Resampling.LANCZOS,
            ).convert("RGBA")
        canvas = self._prepare_room(canvas)
        scale = PACKAGE_SCALE[package_id]
        by_category = {item.category: item for item in decorations}
        focal_x = self._focal_x(request, decorations)
        ground_y = 660
        room_light = self._room_light(canvas)

        if "backdrop" in by_category:
            self._place_asset(
                canvas,
                "backdrop",
                centre=(focal_x, ground_y - 225),
                maximum=(int(620 * scale), int(520 * scale)),
                room_light=room_light,
                shadow=True,
            )
        if "lighting" in by_category:
            lighting_layers = {"essential": 1, "balanced": 1, "statement": 2}[
                package_id
            ]
            for index in range(lighting_layers):
                self._place_asset(
                    canvas,
                    "lighting",
                    centre=(focal_x, 150 + index * 45),
                    maximum=(int(990 * scale), int(300 * scale)),
                    room_light=max(room_light, 1.0),
                    opacity=0.78 if index else 0.94,
                )
        if "floor-arrangement" in by_category:
            self._place_asset(
                canvas,
                "floor-arrangement",
                centre=(focal_x, ground_y - 175),
                maximum=(int(720 * scale), int(430 * scale)),
                room_light=room_light,
                shadow=True,
            )

        # The real cake always needs a credible support surface. If the selected
        # package has table styling, its catalogue cut-out is used; otherwise a
        # quieter version of the same practical table is shown.
        self._place_asset(
            canvas,
            "table-setting",
            centre=(focal_x, ground_y - 90),
            maximum=(int(535 * scale), int(260 * scale)),
            room_light=room_light,
            opacity=1.0 if "table-setting" in by_category else 0.82,
            shadow=True,
        )
        if "signage" in by_category:
            sign_x = max(105, focal_x - int(365 * scale))
            sign_y = ground_y - int(145 * scale)
            sign_box = self._place_asset(
                canvas,
                "signage",
                centre=(sign_x, sign_y),
                maximum=(int(185 * scale), int(330 * scale)),
                room_light=room_light,
                shadow=True,
            )
            if sign_box is not None:
                self._draw_sign_text(canvas, sign_box, request)

        self._paste_cake(
            canvas,
            cake_path,
            centre=(focal_x, ground_y - int(215 * scale)),
            max_size=(int(175 * scale), int(175 * scale)),
            room_light=room_light,
        )
        self._draw_labels(
            canvas,
            package_name=package_name,
            theme_id=request.event.theme_id,
            decoration_cost_pkr=decoration_cost_pkr,
            item_count=len(decorations),
        )
        return canvas.convert("RGB")

    @staticmethod
    def _prepare_room(canvas: Image.Image) -> Image.Image:
        canvas = ImageEnhance.Contrast(canvas).enhance(1.04)
        canvas = ImageEnhance.Color(canvas).enhance(1.03)
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay, "RGBA").rectangle(
            (0, 0, 1280, 720), fill=(255, 244, 232, 14)
        )
        return Image.alpha_composite(canvas, overlay)

    @staticmethod
    def _room_light(canvas: Image.Image) -> float:
        sample = canvas.convert("L").resize((1, 1), Image.Resampling.BILINEAR)
        brightness = sample.getpixel((0, 0)) / 255
        return min(1.08, max(0.76, 0.74 + brightness * 0.5))

    @staticmethod
    def _focal_x(
        request: DesignRequest,
        decorations: list[DecorRecommendation],
    ) -> int:
        for decoration in decorations:
            if decoration.category == "backdrop" and decoration.placements:
                x_m = decoration.placements[0].position.x_m
                ratio = x_m / max(request.space.dimensions.width_m, 0.01)
                return int(min(0.72, max(0.28, ratio)) * CANVAS_SIZE[0])
        return CANVAS_SIZE[0] // 2

    def _place_asset(
        self,
        canvas: Image.Image,
        category: str,
        *,
        centre: tuple[int, int],
        maximum: tuple[int, int],
        room_light: float,
        opacity: float = 1.0,
        shadow: bool = False,
    ) -> tuple[int, int, int, int] | None:
        asset = self.asset_store.load(category)
        if asset is None:
            return None
        asset.thumbnail(maximum, Image.Resampling.LANCZOS)
        rgb = ImageEnhance.Brightness(asset.convert("RGB")).enhance(room_light)
        alpha = asset.getchannel("A")
        if opacity < 1:
            alpha = alpha.point(lambda value: int(value * opacity))
        asset = Image.merge("RGBA", (*rgb.split(), alpha))
        left = int(centre[0] - asset.width / 2)
        top = int(centre[1] - asset.height / 2)
        if shadow:
            self._paste_shadow(canvas, alpha, left, top, asset.height)
        canvas.alpha_composite(asset, (left, top))
        return left, top, left + asset.width, top + asset.height

    @staticmethod
    def _paste_shadow(
        canvas: Image.Image,
        alpha: Image.Image,
        left: int,
        top: int,
        height: int,
    ) -> None:
        shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(5, height // 35)))
        shadow_alpha = shadow_alpha.point(lambda value: int(value * 0.25))
        shadow = Image.new("RGBA", alpha.size, (28, 18, 14, 0))
        shadow.putalpha(shadow_alpha)
        canvas.alpha_composite(shadow, (left + 10, top + 12))

    @staticmethod
    def _paste_cake(
        canvas: Image.Image,
        cake_path: Path,
        *,
        centre: tuple[int, int],
        max_size: tuple[int, int],
        room_light: float,
    ) -> None:
        with Image.open(cake_path) as source:
            cake = ImageOps.fit(
                source.convert("RGB"),
                max_size,
                method=Image.Resampling.LANCZOS,
            )
        cake = ImageEnhance.Brightness(cake).enhance(room_light)
        mask = Image.new("L", cake.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, cake.width - 1, cake.height - 1),
            radius=max(14, cake.width // 8),
            fill=255,
        )
        card = Image.new(
            "RGBA", (cake.width + 16, cake.height + 16), (250, 245, 238, 245)
        )
        card_mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(card_mask).rounded_rectangle(
            (0, 0, card.width - 1, card.height - 1),
            radius=max(18, cake.width // 7),
            fill=255,
        )
        card.paste(cake, (8, 8), mask)
        shadow = Image.new("RGBA", card.size, (25, 16, 12, 0))
        blurred = card_mask.filter(ImageFilter.GaussianBlur(12))
        shadow.putalpha(blurred.point(lambda value: int(value * 0.35)))
        left = centre[0] - card.width // 2
        top = centre[1] - card.height // 2
        canvas.alpha_composite(shadow, (left + 7, top + 10))
        canvas.paste(card, (left, top), card_mask)

    @staticmethod
    def _draw_sign_text(
        canvas: Image.Image,
        box: tuple[int, int, int, int],
        request: DesignRequest,
    ) -> None:
        left, top, right, bottom = box
        draw = ImageDraw.Draw(canvas, "RGBA")
        event_name = request.event.event_type.value.replace("_", " ").title()
        draw.text(
            ((left + right) // 2, top + int((bottom - top) * 0.37)),
            event_name,
            anchor="mm",
            font=_font(max(15, (right - left) // 10), bold=True),
            fill=(84, 55, 43, 238),
        )

    @staticmethod
    def _draw_labels(
        canvas: Image.Image,
        *,
        package_name: str,
        theme_id: str,
        decoration_cost_pkr: int,
        item_count: int,
    ) -> None:
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.rounded_rectangle((24, 22, 478, 132), radius=22, fill=(35, 23, 20, 218))
        draw.text(
            (48, 41),
            package_name,
            font=_font(31, bold=True),
            fill=(255, 255, 255, 255),
        )
        subtitle = (
            f"{theme_id.replace('-', ' ').title()} · {item_count} catalogue "
            f"types · PKR {decoration_cost_pkr:,}"
        )
        draw.text((48, 88), subtitle, font=_font(17), fill=(255, 228, 210, 255))
        draw.rectangle((0, 680, 1280, 720), fill=(32, 24, 21, 224))
        draw.text(
            (640, 700),
            "Photo-grounded concept—not installation scale · Verify all clearances",
            anchor="mm",
            font=_font(18, bold=True),
            fill=(255, 255, 255, 255),
        )
