"""Compose celebration-specific catalogue cut-outs over a real venue photo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.schemas.design import DecorRecommendation, DesignRequest


CANVAS_SIZE = (1280, 720)
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "real_decor"
PACKAGE_SCALE = {"essential": 0.9, "balanced": 1.0, "statement": 1.08}
ASSET_FILES = {
    "backdrop": "backdrop.webp",
    "floor-arrangement": "floor-arrangement.webp",
    "lighting": "lighting.webp",
    "table-setting": "table-setting.webp",
    "signage": "signage.webp",
}
V5_1_ASSET_FILES = {
    (category, style): f"v5_1/{category}-{style}.webp"
    for category in ("backdrop", "floor", "table")
    for style in ("romantic", "modern", "playful")
}
V5_2_STYLES = (
    "rustic", "tropical", "coastal", "mehndi", "wedding", "majlis",
    "winter", "celestial", "retro",
)
V5_2_ASSET_FILES = {
    (category, style): f"v5_2/{category}-{style}.webp"
    for category in ("backdrop", "floor", "table")
    for style in V5_2_STYLES
}
for _category in ("lighting", "signage"):
    for _family in (
        "romantic", "modern", "playful", "natural", "cultural", "seasonal"
    ):
        V5_2_ASSET_FILES[(_category, _family)] = (
            f"v5_2/{_category}-{_family}.webp"
        )

# Every public catalogue theme has an explicit visual treatment. This prevents
# an unknown or newly selected celebration from silently becoming the same
# generic romantic setup.
THEME_VISUAL_STYLE = {
    "rustic-boho": "rustic",
    "modern-minimalist": "modern",
    "classic-elegant": "romantic",
    "tropical": "tropical",
    "vintage-garden": "romantic",
    "glam-gold": "modern",
    "pastel-dreamy": "playful",
    "dark-moody": "celestial",
    "whimsical-kids": "playful",
    "beach-coastal": "coastal",
    "industrial": "modern",
    "floral-romantic": "romantic",
    "retro-70s": "retro",
    "winter-wonderland": "winter",
    "south-asian-mehndi": "mehndi",
    "south-asian-wedding": "wedding",
    "arabian-majlis": "majlis",
    "sports-hobby": "playful",
    "rainbow-bright-pop": "playful",
    "farmhouse": "rustic",
    "art-deco": "modern",
    "enchanted-forest": "tropical",
    "celestial-night": "celestial",
    "corporate-brand": "modern",
    "baby-safari": "rustic",
    "candy-pop": "playful",
}
STYLE_FAMILY = {
    "romantic": "romantic",
    "modern": "modern",
    "playful": "playful",
    "rustic": "natural",
    "tropical": "natural",
    "coastal": "natural",
    "mehndi": "cultural",
    "wedding": "cultural",
    "majlis": "cultural",
    "winter": "seasonal",
    "celestial": "seasonal",
    "retro": "seasonal",
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

    def load(self, category: str, style: str | None = None) -> Image.Image | None:
        filename = V5_2_ASSET_FILES.get((category, style)) if style else None
        filename = filename or (
            V5_1_ASSET_FILES.get((category, style)) if style else None
        )
        filename = filename or ASSET_FILES.get(category)
        if filename is None:
            return None
        path = self.asset_dir / filename
        if not path.is_file():
            return None
        with Image.open(path) as source:
            image = source.convert("RGBA")
        if image.getchannel("A").getextrema()[0] == 255:
            raise ValueError(f"preview asset '{filename}' has no transparency")
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
        selected_theme_id: str | None = None,
        decorations: list[DecorRecommendation],
        palette_hex: str,
        decoration_cost_pkr: int,
    ) -> Image.Image:
        if package_id not in PACKAGE_SCALE:
            raise ValueError("unknown design package")
        with Image.open(venue_path) as venue_source:
            canvas = ImageOps.fit(
                venue_source.convert("RGB"),
                CANVAS_SIZE,
                method=Image.Resampling.LANCZOS,
            ).convert("RGBA")
        canvas = self._prepare_room(canvas)
        scale = PACKAGE_SCALE[package_id]
        palette = self._palette(palette_hex)
        theme_id = selected_theme_id or request.event.theme_id
        style = self._style_family(request, theme_id)
        family = STYLE_FAMILY[style]
        composition = self._composition(request, package_id)
        by_category = {item.category: item for item in decorations}
        layout = self._layout(request, decorations, scale)
        focal_x = layout["focal_x"]
        ground_y = layout["ground_y"]
        room_light = self._room_light(canvas)

        if "backdrop" in by_category:
            self._place_asset(
                canvas,
                "backdrop",
                style=style,
                centre=(focal_x, ground_y - layout["backdrop_height"] // 2),
                maximum=(layout["backdrop_width"], layout["backdrop_height"]),
                room_light=room_light,
                palette=palette,
                shadow=True,
            )
        if "lighting" in by_category:
            lighting_layers = composition["lighting_layers"]
            for index in range(lighting_layers):
                self._place_asset(
                    canvas,
                    "lighting",
                    style=family,
                    centre=(focal_x, 150 + index * 45),
                    maximum=(int(990 * scale), int(300 * scale)),
                    room_light=max(room_light, 1.0),
                    palette=palette,
                    opacity=0.78 if index else 0.94,
                )
        if "floor-arrangement" in by_category:
            count = composition["floor_count"]
            spread = layout["backdrop_width"] * 0.46
            positions = {
                1: (focal_x + int(spread * 0.72),),
                2: (focal_x - int(spread), focal_x + int(spread)),
                3: (focal_x - int(spread), focal_x, focal_x + int(spread)),
            }[count]
            for index, centre_x in enumerate(positions):
                cluster_scale = 0.88 if count == 3 and index == 1 else 1.0
                self._place_asset(
                    canvas,
                    "floor",
                    style=style,
                    centre=(centre_x, ground_y - int(layout["floor_height"] * 0.42)),
                    maximum=(
                        int(layout["floor_width"] * cluster_scale),
                        int(layout["floor_height"] * cluster_scale),
                    ),
                    room_light=room_light,
                    palette=palette,
                    mirror=index % 2 == 1,
                    shadow=True,
                )

        # The real cake always needs a credible support surface. If the selected
        # package has table styling, its catalogue cut-out is used; otherwise a
        # quieter version of the same practical table is shown.
        self._place_asset(
            canvas,
            "table",
            style=style,
            centre=(focal_x, ground_y - layout["table_height"] // 2),
            maximum=(layout["table_width"], layout["table_height"]),
            room_light=room_light,
            palette=palette,
            opacity=1.0 if "table-setting" in by_category else 0.82,
            shadow=True,
        )
        if "signage" in by_category:
            sign_x = focal_x + composition["sign_direction"] * int(
                layout["backdrop_width"] * 0.56
            )
            sign_x = min(1175, max(105, sign_x))
            sign_y = ground_y - int(145 * scale)
            sign_box = self._place_asset(
                canvas,
                "signage",
                style=family,
                centre=(sign_x, sign_y),
                maximum=(int(185 * scale), int(330 * scale)),
                room_light=room_light,
                palette=palette,
                shadow=True,
            )
            if sign_box is not None:
                self._draw_sign_text(canvas, sign_box, request)

        self._paste_cake(
            canvas,
            cake_path,
            centre=(focal_x, ground_y - layout["table_height"] - int(72 * scale)),
            max_size=(int(205 * scale), int(205 * scale)),
            room_light=room_light,
        )
        self._draw_labels(
            canvas,
            package_name=package_name,
            theme_id=theme_id,
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

    @staticmethod
    def _style_family(request: DesignRequest, theme: str | None = None) -> str:
        theme = theme or request.event.theme_id
        event = request.event.event_type.value
        if theme in THEME_VISUAL_STYLE:
            return THEME_VISUAL_STYLE[theme]
        if event in {"kids_birthday", "baby_shower"}:
            return "playful"
        if event == "corporate":
            return "modern"
        if event in {"wedding", "engagement"}:
            return "wedding"
        return "romantic"

    @staticmethod
    def _composition(request: DesignRequest, package_id: str) -> dict[str, int]:
        """Vary density and balance by both package and celebration type."""
        event = request.event.event_type.value
        floor_count = {"essential": 1, "balanced": 2, "statement": 3}[package_id]
        lighting_layers = 2 if package_id == "statement" else 1
        sign_direction = -1
        if event == "corporate":
            floor_count = {"essential": 1, "balanced": 1, "statement": 2}[
                package_id
            ]
            lighting_layers = 1
            sign_direction = 1
        elif event in {"wedding", "engagement", "anniversary"}:
            floor_count = 3 if package_id == "statement" else 2
        elif event in {"kids_birthday", "baby_shower"}:
            lighting_layers = 1
        return {
            "floor_count": floor_count,
            "lighting_layers": lighting_layers,
            "sign_direction": sign_direction,
        }

    @staticmethod
    def _palette(palette_hex: str) -> tuple[int, int, int] | None:
        for value in palette_hex.replace(",", ";").split(";"):
            value = value.strip().lstrip("#")
            if len(value) == 6:
                try:
                    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
                except ValueError:
                    continue
        return None

    def _layout(
        self,
        request: DesignRequest,
        decorations: list[DecorRecommendation],
        scale: float,
    ) -> dict[str, int]:
        room_width = max(request.space.dimensions.width_m, 1.5)
        room_height = max(request.space.dimensions.height_m, 1.8)
        pixels_per_metre_x = min(520.0, 1160.0 / room_width)
        # The visible floor-to-ceiling region occupies about 625 pixels. Use
        # the customer's height as the second scale axis instead of deriving
        # every dimension from room width.
        pixels_per_metre_y = 625.0 / room_height

        def dimensions(category: str, default: tuple[float, float]) -> tuple[float, float]:
            for item in decorations:
                if item.category == category and item.placements:
                    value = item.placements[0].dimensions
                    if value is not None:
                        return value.width_m, value.height_m
            return default

        backdrop_m = dimensions("backdrop", (min(2.4, room_width * 0.78), 2.1))
        table_m = dimensions("table-setting", (min(1.5, room_width * 0.52), 0.9))
        setup_width = min(1160, max(560, int(backdrop_m[0] * pixels_per_metre_x * scale)))
        target_height_m = min(room_height * 0.9, max(backdrop_m[1], room_height * 0.76))
        setup_height = min(610, max(475, int(target_height_m * pixels_per_metre_y * scale)))
        focal_x = self._focal_x(request, decorations)
        half = setup_width // 2
        focal_x = min(CANVAS_SIZE[0] - half - 35, max(half + 35, focal_x))
        return {
            "focal_x": focal_x,
            "ground_y": 665,
            "backdrop_width": setup_width,
            "backdrop_height": setup_height,
            "table_width": min(int(setup_width * 0.62), max(500, int(table_m[0] * pixels_per_metre_x * scale))),
            "table_height": min(330, max(245, int(table_m[1] * pixels_per_metre_y * scale))),
            "floor_width": min(330, max(230, int(setup_width * 0.29))),
            "floor_height": min(260, max(175, int(setup_height * 0.39))),
        }

    def _place_asset(
        self,
        canvas: Image.Image,
        category: str,
        *,
        style: str | None = None,
        centre: tuple[int, int],
        maximum: tuple[int, int],
        room_light: float,
        palette: tuple[int, int, int] | None = None,
        opacity: float = 1.0,
        mirror: bool = False,
        shadow: bool = False,
    ) -> tuple[int, int, int, int] | None:
        asset = self.asset_store.load(category, style)
        if asset is None:
            return None
        # Stage 5.2 files intentionally have transparent canvases. Crop that
        # invisible margin before thumbnailing so the visible décor, rather
        # than its empty canvas, fills the requested physical dimensions.
        bounds = asset.getchannel("A").getbbox()
        if bounds is not None:
            asset = asset.crop(bounds)
        asset.thumbnail(maximum, Image.Resampling.LANCZOS)
        if mirror:
            asset = ImageOps.mirror(asset)
        rgb = ImageEnhance.Brightness(asset.convert("RGB")).enhance(room_light)
        if palette is not None:
            wash = Image.new("RGB", rgb.size, palette)
            rgb = Image.blend(rgb, wash, 0.1)
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
            cake = source.convert("RGBA")
        # Background extraction is performed on a bounded working copy. Phone
        # uploads can be several megapixels, while the final cake is about 200
        # pixels tall; processing the full upload three times would add delay
        # without improving the preview.
        cake.thumbnail(
            (max_size[0] * 3, max_size[1] * 3),
            Image.Resampling.LANCZOS,
        )
        cake = PhotoPreviewBuilder._extract_cake(cake)
        cake.thumbnail(max_size, Image.Resampling.LANCZOS)
        rgb = ImageEnhance.Brightness(cake.convert("RGB")).enhance(room_light)
        cake = Image.merge("RGBA", (*rgb.split(), cake.getchannel("A")))
        mask = cake.getchannel("A")
        shadow = Image.new("RGBA", cake.size, (25, 16, 12, 0))
        blurred = mask.filter(ImageFilter.GaussianBlur(12))
        shadow.putalpha(blurred.point(lambda value: int(value * 0.35)))
        left = centre[0] - cake.width // 2
        top = centre[1] - cake.height // 2
        canvas.alpha_composite(shadow, (left + 7, top + 10))
        canvas.alpha_composite(cake, (left, top))

    @staticmethod
    def _extract_cake(source: Image.Image) -> Image.Image:
        """Remove a mostly uniform photo background without an external model."""
        rgba = source.convert("RGBA")
        existing = rgba.getchannel("A")
        if existing.getextrema()[0] < 245:
            bounds = existing.getbbox()
            return rgba.crop(bounds) if bounds else rgba
        rgb = rgba.convert("RGB")
        width, height = rgb.size
        corners = [rgb.getpixel(point) for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]
        background = tuple(sorted(pixel[channel] for pixel in corners)[len(corners) // 2] for channel in range(3))
        difference = Image.new("L", rgb.size)
        difference.putdata([
            min(255, int(sum((pixel[channel] - background[channel]) ** 2 for channel in range(3)) ** 0.5 * 2.5))
            for pixel in rgb.getdata()
        ])
        mask = difference.point(lambda value: 255 if value >= 48 else 0)
        mask = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(2.2))
        bounds = mask.getbbox()
        if bounds is None or (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) < width * height * 0.04:
            return rgba
        rgba.putalpha(mask)
        return rgba.crop(bounds)

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
