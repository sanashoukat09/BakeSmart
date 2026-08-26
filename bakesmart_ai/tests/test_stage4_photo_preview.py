import csv
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from app.schemas.design import DecorRecommendation, DesignRequest, EventType
from app.services.photo_preview_builder import (
    ASSET_FILES,
    STYLE_FAMILY,
    THEME_VISUAL_STYLE,
    V5_1_ASSET_FILES,
    V5_2_ASSET_FILES,
    PhotoPreviewBuilder,
    PreviewAssetStore,
)


def _decor(category: str, index: int) -> DecorRecommendation:
    role = {
        "backdrop": "backdrop",
        "lighting": "lighting",
        "signage": "signage",
    }.get(category, "decoration")
    return DecorRecommendation.model_validate(
        {
            "catalog_id": f"stage4-{category}",
            "name": f"Stage 4 {category}",
            "category": category,
            "quantity": 1,
            "unit_cost_pkr": 5000 + index,
            "placements": [
                {
                    "asset_id": f"real-catalog/stage4-{category}",
                    "role": role,
                    "catalog_id": f"stage4-{category}",
                    "position": {"x_m": 1.5, "y_m": 0.1, "z_m": 0},
                    "dimensions": {
                        "width_m": 1.5,
                        "depth_m": 0.4,
                        "height_m": 1.8,
                    },
                }
            ],
        }
    )


def test_stage4_assets_have_real_transparency():
    store = PreviewAssetStore()
    for category in ASSET_FILES:
        asset = store.load(category)
        assert asset is not None
        low, high = asset.getchannel("A").getextrema()
        assert low == 0
        assert high > 200
    for (category, style), _filename in V5_1_ASSET_FILES.items():
        asset = store.load(category, style)
        assert asset is not None
        low, high = asset.getchannel("A").getextrema()
        assert low == 0
        assert high > 200
    for (category, style), _filename in V5_2_ASSET_FILES.items():
        asset = store.load(category, style)
        assert asset is not None
        low, high = asset.getchannel("A").getextrema()
        assert low == 0
        assert high > 200


def test_stage52_maps_every_catalogue_theme_to_available_assets():
    catalogue = Path(__file__).parents[1] / "data" / "catalogs" / "themes.csv"
    with catalogue.open(newline="", encoding="utf-8") as source:
        theme_ids = {row["theme_id"] for row in csv.DictReader(source)}
    assert theme_ids == set(THEME_VISUAL_STYLE)

    store = PreviewAssetStore()
    for theme_id, style in THEME_VISUAL_STYLE.items():
        for category in ("backdrop", "floor", "table"):
            assert store.load(category, style) is not None, (theme_id, category)
        family = STYLE_FAMILY[style]
        for category in ("lighting", "signage"):
            assert store.load(category, family) is not None, (theme_id, category)


def test_stage52_varies_composition_by_event(valid_design_request):
    request = DesignRequest.model_validate(valid_design_request)
    builder = PhotoPreviewBuilder()

    def for_event(event_type: str) -> dict[str, int]:
        changed = request.model_copy(
            update={
                "event": request.event.model_copy(
                    update={"event_type": EventType(event_type)}
                )
            }
        )
        return builder._composition(changed, "statement")

    assert for_event("corporate") == {
        "floor_count": 2,
        "lighting_layers": 1,
        "sign_direction": 1,
    }
    assert for_event("wedding")["floor_count"] == 3
    assert for_event("kids_birthday")["lighting_layers"] == 1


def test_stage51_selects_distinct_theme_families_and_room_relative_scale(
    valid_design_request,
):
    request = DesignRequest.model_validate(valid_design_request)
    builder = PhotoPreviewBuilder()
    romantic = request.model_copy(
        update={"event": request.event.model_copy(update={"theme_id": "floral-romantic"})}
    )
    modern = request.model_copy(
        update={"event": request.event.model_copy(update={"theme_id": "modern-minimalist"})}
    )
    playful = request.model_copy(
        update={"event": request.event.model_copy(update={"theme_id": "rainbow-bright-pop"})}
    )
    assert builder._style_family(romantic) == "romantic"
    assert builder._style_family(modern) == "modern"
    assert builder._style_family(playful) == "playful"

    decorations = [_decor("backdrop", 0), _decor("table-setting", 1)]
    compact_layout = builder._layout(request, decorations, 1.0)
    larger_space = request.model_copy(
        update={
            "space": request.space.model_copy(
                update={
                    "dimensions": request.space.dimensions.model_copy(
                        update={"width_m": request.space.dimensions.width_m * 2}
                    )
                }
            )
        }
    )
    large_layout = builder._layout(larger_space, decorations, 1.0)
    assert compact_layout["backdrop_width"] > large_layout["backdrop_width"]
    assert 0 < compact_layout["focal_x"] < 1280


def test_stage53_uses_backend_selected_theme_and_room_height(valid_design_request):
    request = DesignRequest.model_validate(valid_design_request)
    builder = PhotoPreviewBuilder()
    assert builder._style_family(request, "south-asian-mehndi") == "mehndi"
    assert builder._style_family(request, "corporate-brand") == "modern"

    decorations = [_decor("backdrop", 0), _decor("table-setting", 1)]
    low_room = request.model_copy(
        update={
            "space": request.space.model_copy(
                update={
                    "dimensions": request.space.dimensions.model_copy(
                        update={"height_m": 2.0}
                    )
                }
            )
        }
    )
    tall_room = request.model_copy(
        update={
            "space": request.space.model_copy(
                update={
                    "dimensions": request.space.dimensions.model_copy(
                        update={"height_m": 4.0}
                    )
                }
            )
        }
    )
    low_layout = builder._layout(low_room, decorations, 1.0)
    tall_layout = builder._layout(tall_room, decorations, 1.0)
    assert 475 <= low_layout["backdrop_height"] <= 610
    assert 475 <= tall_layout["backdrop_height"] <= 610
    assert low_layout["table_height"] > tall_layout["table_height"]


def test_stage53_extracts_cake_without_square_photo_card():
    source = Image.new("RGBA", (300, 300), (245, 245, 242, 255))
    draw = ImageDraw.Draw(source)
    draw.rectangle((92, 92, 208, 260), fill=(86, 42, 30, 255))
    draw.ellipse((75, 60, 225, 130), fill=(130, 67, 48, 255))
    extracted = PhotoPreviewBuilder._extract_cake(source)
    assert extracted.width < source.width
    assert extracted.height < source.height
    assert extracted.getchannel("A").getextrema()[0] == 0


def test_stage4_builds_three_visibly_different_real_photo_composites(
    tmp_path: Path,
    valid_design_request,
):
    venue_path = tmp_path / "venue.png"
    cake_path = tmp_path / "cake.png"
    Image.new("RGB", (1600, 900), (202, 215, 220)).save(venue_path)
    cake = Image.new("RGB", (500, 500), (238, 225, 210))
    cake.paste((92, 43, 31), (145, 80, 355, 450))
    cake.save(cake_path)
    request = DesignRequest.model_validate(valid_design_request)
    builder = PhotoPreviewBuilder()
    category_sets = {
        "essential": ["backdrop", "table-setting"],
        "balanced": ["backdrop", "table-setting", "lighting", "signage"],
        "statement": list(ASSET_FILES),
    }
    outputs = {}
    for package_id, categories in category_sets.items():
        outputs[package_id] = builder.build(
            venue_path=venue_path,
            cake_path=cake_path,
            request=request,
            package_id=package_id,
            package_name=package_id.title(),
            decorations=[_decor(category, index) for index, category in enumerate(categories)],
            palette_hex="#F0B6C1,#F7E9D7,#C9A24D",
            decoration_cost_pkr=20_000,
        )
        assert outputs[package_id].size == (1280, 720)
        assert outputs[package_id].mode == "RGB"

    assert ImageChops.difference(outputs["essential"], outputs["balanced"]).getbbox()
    assert ImageChops.difference(outputs["balanced"], outputs["statement"]).getbbox()
    # The customer's venue still supplies untouched visual evidence away from
    # the composition and labels; it has not been replaced by a generated room.
    corner = outputs["balanced"].getpixel((1200, 620))
    assert corner[2] >= corner[0]
