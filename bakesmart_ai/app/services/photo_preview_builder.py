"""Build Stage 1 concept previews from the customer's real venue and cake photos."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from app.schemas.design import DecorRecommendation, DesignRequest


CANVAS_SIZE = (1280, 720)
PACKAGE_DENSITY = {"essential": 1, "balanced": 2, "statement": 3}
NAMED_COLOURS = {
    "blush": (226, 166, 175),
    "pink": (232, 155, 180),
    "cream": (249, 239, 213),
    "gold": (201, 162, 78),
    "blue": (91, 143, 194),
    "navy": (35, 54, 86),
    "green": (91, 132, 92),
    "sage": (151, 166, 139),
    "purple": (132, 94, 153),
    "lavender": (181, 159, 207),
    "red": (174, 62, 58),
    "orange": (218, 127, 65),
    "yellow": (231, 196, 88),
    "black": (35, 35, 35),
    "white": (245, 245, 242),
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


def _palette(values: str) -> list[tuple[int, int, int]]:
    colours: list[tuple[int, int, int]] = []
    for raw in values.replace(";", ",").split(","):
        value = raw.strip().lstrip("#")
        if len(value) != 6:
            continue
        try:
            colours.append(tuple(int(value[index : index + 2], 16) for index in (0, 2, 4)))
        except ValueError:
            continue
    return colours or [(176, 94, 39), (255, 232, 213), (74, 43, 32)]


class PhotoPreviewBuilder:
    """Compose an honest, shareable concept image without pretending it is AR."""

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
        if package_id not in PACKAGE_DENSITY:
            raise ValueError("unknown design package")
        colours = self._preferred_palette(
            request.event.preferred_colors,
            request.event.excluded_colors,
            palette_hex,
        )
        with Image.open(venue_path) as venue_source:
            canvas = ImageOps.fit(
                venue_source.convert("RGB"),
                CANVAS_SIZE,
                method=Image.Resampling.LANCZOS,
            )
        canvas = ImageEnhance.Brightness(canvas).enhance(0.78).convert("RGBA")
        overlay = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        density = PACKAGE_DENSITY[package_id]
        categories = {item.category for item in decorations}

        # A translucent focal panel keeps the real room visible instead of replacing it.
        focal_left, focal_top, focal_right, focal_bottom = 330, 105, 950, 590
        if "backdrop" in categories:
            draw.rounded_rectangle(
                (focal_left, focal_top, focal_right, focal_bottom),
                radius=110,
                fill=(*colours[0], 118),
                outline=(255, 255, 255, 205),
                width=7,
            )
            if density >= 2:
                draw.arc(
                    (focal_left + 55, focal_top + 35, focal_right - 55, focal_bottom + 75),
                    180,
                    360,
                    fill=(*colours[min(1, len(colours) - 1)], 225),
                    width=18,
                )

        if "lighting" in categories:
            self._draw_lights(draw, colours, density)

        table_y = 500
        draw.rounded_rectangle((440, table_y, 840, 625), radius=18, fill=(242, 232, 221, 235))
        draw.rectangle((465, 620, 500, 700), fill=(92, 61, 48, 230))
        draw.rectangle((780, 620, 815, 700), fill=(92, 61, 48, 230))

        if "floor-arrangement" in categories:
            self._draw_arrangements(draw, colours, density)
        if "signage" in categories:
            title = request.event.event_type.value.replace("_", " ").title()
            draw.rounded_rectangle((490, 170, 790, 255), radius=20, fill=(255, 255, 255, 205))
            draw.text(
                (640, 212),
                title,
                anchor="mm",
                font=_font(31, bold=True),
                fill=(69, 43, 34, 255),
            )

        canvas = Image.alpha_composite(canvas, overlay)
        canvas = self._paste_cake(canvas, cake_path, centre=(640, 472), max_size=(225, 215))
        self._draw_labels(
            canvas,
            package_name=package_name,
            theme_id=request.event.theme_id,
            decoration_cost_pkr=decoration_cost_pkr,
        )
        return canvas.convert("RGB")

    @staticmethod
    def _preferred_palette(
        preferred: list[str],
        excluded: list[str],
        palette_hex: str,
    ) -> list[tuple[int, int, int]]:
        selected: list[tuple[int, int, int]] = []
        excluded_names = " ".join(excluded).lower().replace("-", " ")
        for value in preferred:
            normalized = value.lower().replace("-", " ")
            for name, colour in NAMED_COLOURS.items():
                if (
                    name in normalized
                    and name not in excluded_names
                    and colour not in selected
                ):
                    selected.append(colour)
                    break
        return [*selected, *_palette(palette_hex)][:6]

    @staticmethod
    def _draw_lights(
        draw: ImageDraw.ImageDraw,
        colours: list[tuple[int, int, int]],
        density: int,
    ) -> None:
        strands = density
        for strand in range(strands):
            y = 82 + strand * 40
            draw.arc((170, y - 55, 1110, y + 80), 5, 175, fill=(255, 239, 185, 235), width=4)
            bulbs = 8 + density * 2
            for index in range(bulbs):
                x = 210 + index * (860 // max(1, bulbs - 1))
                drop = 18 + ((index + strand) % 3) * 8
                colour = colours[(index + strand) % len(colours)]
                draw.line((x, y, x, y + drop), fill=(255, 244, 205, 215), width=3)
                draw.ellipse((x - 8, y + drop - 4, x + 8, y + drop + 12), fill=(*colour, 240))

    @staticmethod
    def _draw_arrangements(
        draw: ImageDraw.ImageDraw,
        colours: list[tuple[int, int, int]],
        density: int,
    ) -> None:
        for side in (-1, 1):
            centre_x = 390 if side < 0 else 890
            count = 5 + density * 4
            for index in range(count):
                x = centre_x + ((index % 4) - 1) * 30
                y = 550 - (index // 4) * 30 + (index % 2) * 8
                radius = 15 + (index % 3) * 4
                colour = colours[index % len(colours)]
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*colour, 225))
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 244, 217, 245))
            draw.line((centre_x, 570, centre_x - side * 15, 642), fill=(64, 101, 70, 230), width=7)

    @staticmethod
    def _paste_cake(
        canvas: Image.Image,
        cake_path: Path,
        *,
        centre: tuple[int, int],
        max_size: tuple[int, int],
    ) -> Image.Image:
        with Image.open(cake_path) as source:
            cake = source.convert("RGB")
        cake.thumbnail(max_size, Image.Resampling.LANCZOS)
        card = Image.new("RGBA", (cake.width + 20, cake.height + 20), (255, 255, 255, 232))
        mask = Image.new("L", card.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, card.width - 1, card.height - 1),
            radius=22,
            fill=255,
        )
        card.paste(cake, (10, 10))
        left = centre[0] - card.width // 2
        top = centre[1] - card.height // 2
        canvas.paste(card, (left, top), mask)
        return canvas

    @staticmethod
    def _draw_labels(
        canvas: Image.Image,
        *,
        package_name: str,
        theme_id: str,
        decoration_cost_pkr: int,
    ) -> None:
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.rounded_rectangle((25, 25, 460, 145), radius=24, fill=(35, 23, 20, 220))
        draw.text((50, 46), package_name, font=_font(34, bold=True), fill=(255, 255, 255, 255))
        subtitle = f"{theme_id.replace('-', ' ').title()} • PKR {decoration_cost_pkr:,} decor"
        draw.text((50, 94), subtitle, font=_font(20), fill=(255, 228, 210, 255))
        draw.rectangle((0, 675, 1280, 720), fill=(32, 24, 21, 225))
        draw.text(
            (640, 697),
            "Concept preview—not to scale • Uses your venue and cake photos • "
            "Verify physical clearances",
            anchor="mm",
            font=_font(19, bold=True),
            fill=(255, 255, 255, 255),
        )
