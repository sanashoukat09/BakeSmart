"""Read-only access to BakeSmart's versioned theme, cake and decor catalogues."""

from __future__ import annotations

import csv
from pathlib import Path

from training.validate_datasets import DEFAULT_DATA_DIR


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _event_matches(row: dict[str, str], event_type: str) -> bool:
    normalized = event_type.replace("_", "-")
    if normalized == "kids-birthday":
        normalized = "birthday"
    return normalized in row["event_types"].split(";")


class CatalogStore:
    """Validated catalogue rows used to turn labels into scene items."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        catalog_dir = data_dir / "catalogs"
        self.themes = {
            row["theme_id"]: row for row in _read_csv(catalog_dir / "themes.csv")
        }
        self.decorations = _read_csv(catalog_dir / "decorations.csv")
        self.cakes = _read_csv(catalog_dir / "cake_designs.csv")
        self.assets = _read_csv(catalog_dir / "ar_assets.csv")
        if not self.themes or not self.decorations or not self.cakes:
            raise ValueError("one or more required design catalogues are empty")

    def has_theme(self, theme_id: str) -> bool:
        return theme_id in self.themes

    def decor_for(
        self,
        theme_id: str,
        event_type: str,
        environment: str,
    ) -> list[dict[str, str]]:
        theme_candidates = [
            row
            for row in self.decorations
            if row["theme_id"] == theme_id
        ]
        candidates = [
            row for row in theme_candidates if _event_matches(row, event_type)
        ] or theme_candidates
        compatible: list[dict[str, str]] = []
        for row in candidates:
            allowed = row["indoor_outdoor"]
            if environment == "indoor" and "indoor" in allowed:
                compatible.append(row)
            elif environment == "outdoor" and "outdoor" in allowed:
                compatible.append(row)
            elif environment == "semi_outdoor" and (
                "indoor" in allowed or "outdoor" in allowed
            ):
                compatible.append(row)
        return compatible

    def cakes_for(self, theme_id: str, event_type: str) -> list[dict[str, str]]:
        return [
            row
            for row in self.cakes
            if row["theme_id"] == theme_id and _event_matches(row, event_type)
        ]
