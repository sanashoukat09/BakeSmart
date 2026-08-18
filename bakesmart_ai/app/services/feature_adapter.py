"""Convert validated BakeSmart requests into the locked Phase 4 feature order."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.schemas.design import DesignRequest, EventType, VenueType
from training.prepare_dataset import DEFAULT_OUTPUT_DIR
from training.preprocessing import UNKNOWN_CATEGORY


EVENT_MAPPING = {
    EventType.ANNIVERSARY: "anniversary",
    EventType.BABY_SHOWER: "baby_shower",
    EventType.BIRTHDAY: "birthday",
    EventType.KIDS_BIRTHDAY: "birthday",
    EventType.WEDDING: "wedding",
}

VENUE_MAPPING = {
    VenueType.HALL: "hall",
    VenueType.LIVING_ROOM: "home",
    VenueType.BEDROOM: "home",
    VenueType.RESTAURANT: "restaurant",
    VenueType.GARDEN: "outdoor",
    VenueType.ROOFTOP: "outdoor",
}

STYLE_KEYWORDS = {
    "rustic": ("rustic", "boho", "farmhouse", "forest", "coastal"),
    "minimal": ("minimal", "modern", "industrial", "corporate"),
    "traditional": ("south-asian", "mehndi", "arabian", "traditional"),
    "elegant": (
        "elegant",
        "gold",
        "glam",
        "floral-romantic",
        "vintage",
        "art-deco",
        "winter",
        "celestial",
    ),
    "colourful": (
        "tropical",
        "pastel",
        "whimsical",
        "rainbow",
        "retro",
        "sports",
        "candy",
        "safari",
    ),
}

COLOR_KEYWORDS = {
    "blue": ("blue", "navy", "azure", "teal"),
    "gold": ("gold", "brass", "champagne"),
    "green": ("green", "sage", "emerald", "olive"),
    "pink": ("pink", "blush", "rose"),
    "purple": ("purple", "lavender", "lilac", "violet"),
    "red": ("red", "burgundy", "maroon"),
    "white": ("white", "cream", "ivory"),
}


@dataclass(frozen=True)
class AdaptedFeatures:
    matrix: np.ndarray
    warnings: tuple[str, ...]
    derived_values: dict[str, float | str]


class RequestFeatureAdapter:
    """Apply the frozen training statistics without refitting them at runtime."""

    def __init__(self, metadata: dict[str, object]) -> None:
        self.metadata = metadata
        self.feature_columns = list(metadata["feature_columns"])

    @classmethod
    def load(
        cls, processed_dir: Path = DEFAULT_OUTPUT_DIR
    ) -> "RequestFeatureAdapter":
        metadata = json.loads(
            (processed_dir / "preprocessing.json").read_text(encoding="utf-8")
        )
        if metadata.get("fitted_split") != "train":
            raise ValueError("runtime preprocessing metadata was not fitted on train")
        return cls(metadata)

    def transform(self, request: DesignRequest) -> AdaptedFeatures:
        raw_values = self._raw_values(request)
        encoded: dict[str, float] = {}
        warnings: list[str] = []

        numeric_statistics = self.metadata["numeric_statistics"]
        for field in self.metadata["numeric_features"]:
            value = float(raw_values[field])
            statistics = numeric_statistics[field]
            if value < statistics["minimum"] or value > statistics["maximum"]:
                warnings.append(
                    f"{field} is outside the synthetic training range; confidence may be lower."
                )
            encoded[f"num__{field}"] = (
                value - statistics["mean"]
            ) / statistics["standard_deviation"]

        vocabularies = self.metadata["categorical_vocabularies"]
        for field in self.metadata["categorical_features"]:
            vocabulary = vocabularies[field]
            actual = str(raw_values[field])
            selected = actual if actual in vocabulary else UNKNOWN_CATEGORY
            for value in vocabulary:
                suffix = "unknown" if value == UNKNOWN_CATEGORY else value
                encoded[f"cat__{field}__{suffix}"] = float(value == selected)

        matrix = np.asarray(
            [[encoded[column] for column in self.feature_columns]],
            dtype=np.float64,
        )
        if not np.isfinite(matrix).all():
            raise ValueError("request preprocessing produced non-finite features")
        return AdaptedFeatures(matrix, tuple(warnings), raw_values)

    @staticmethod
    def _raw_values(request: DesignRequest) -> dict[str, float | str]:
        dimensions = request.space.dimensions
        if dimensions.depth_m is None:
            room_length = dimensions.width_m
            room_width = dimensions.height_m
            room_area = dimensions.width_m * dimensions.height_m
        else:
            room_length = max(dimensions.width_m, dimensions.depth_m)
            room_width = min(dimensions.width_m, dimensions.depth_m)
            room_area = dimensions.width_m * dimensions.depth_m

        budget = float(request.decoration_budget_pkr)
        guests = float(request.event.guest_count)
        event_type = EVENT_MAPPING.get(request.event.event_type, UNKNOWN_CATEGORY)
        venue_type = VENUE_MAPPING.get(request.space.venue_type, UNKNOWN_CATEGORY)
        age_group = RequestFeatureAdapter._age_group(request.event.event_type)
        preferred_color = RequestFeatureAdapter._preferred_color(
            request.event.preferred_colors
        )
        preferred_style = RequestFeatureAdapter._preferred_style(
            request.event.theme_id
        )
        return {
            "guest_count": guests,
            "room_length_m": room_length,
            "room_width_m": room_width,
            "room_area_m2": room_area,
            "budget_pkr": budget,
            "budget_per_guest_pkr": float(round(budget / guests)),
            "space_per_guest_m2": room_area / guests,
            "budget_per_area_pkr": budget / room_area,
            "event_type": event_type,
            "venue_type": venue_type,
            "age_group": age_group,
            "time_of_day": UNKNOWN_CATEGORY,
            "preferred_color": preferred_color,
            "preferred_style": preferred_style,
        }

    @staticmethod
    def _age_group(event_type: EventType) -> str:
        if event_type == EventType.KIDS_BIRTHDAY:
            return "child"
        if event_type in {EventType.WEDDING, EventType.BABY_SHOWER}:
            return "mixed"
        if event_type == EventType.OTHER:
            return UNKNOWN_CATEGORY
        return "adult"

    @staticmethod
    def _preferred_color(colors: list[str]) -> str:
        matches: list[str] = []
        for color in colors:
            normalized = color.lower().replace("_", "-")
            for label, keywords in COLOR_KEYWORDS.items():
                if any(keyword in normalized for keyword in keywords):
                    matches.append(label)
                    break
        unique = list(dict.fromkeys(matches))
        if len(unique) > 1:
            return "mixed"
        if unique:
            return unique[0]
        return UNKNOWN_CATEGORY

    @staticmethod
    def _preferred_style(theme_id: str) -> str:
        for label, keywords in STYLE_KEYWORDS.items():
            if any(keyword in theme_id for keyword in keywords):
                return label
        return UNKNOWN_CATEGORY
