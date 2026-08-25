"""Read-only Stage 2 catalogue for real-world decoration components.

The catalogue intentionally is not wired into the customer recommendation
endpoint yet.  Stage 3 will rank these validated components using the event,
venue, budget and theme inputs.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_REAL_DECOR_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "real_decor_catalog_v1"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _tokens(value: str) -> set[str]:
    return {token.strip() for token in value.split(";") if token.strip()}


def _normalize_event(event_type: str) -> str:
    normalized = event_type.strip().lower().replace("_", "-")
    return "birthday" if normalized == "kids-birthday" else normalized


@dataclass(frozen=True)
class CatalogueSelection:
    """A deterministic Stage 2 filter result; it is not a recommendation rank."""

    items: tuple[dict[str, str], ...]
    total_price_min_pkr: int
    total_price_max_pkr: int


class RealDecorCatalog:
    """Load real-world item archetypes and their evidence relationships."""

    def __init__(self, catalog_dir: Path = DEFAULT_REAL_DECOR_DIR) -> None:
        self.catalog_dir = catalog_dir
        self.items = _read_csv(catalog_dir / "decor_items.csv")
        self.market_sources = {
            row["source_id"]: row
            for row in _read_csv(catalog_dir / "market_sources.csv")
        }
        self.photo_candidates = {
            row["candidate_id"]: row
            for row in _read_csv(catalog_dir / "photo_candidates.csv")
        }
        self.safety_profiles = {
            row["safety_profile_id"]: row
            for row in _read_csv(catalog_dir / "safety_profiles.csv")
        }
        if not self.items:
            raise ValueError("the Stage 2 decoration catalogue is empty")

    def filter_items(
        self,
        *,
        event_type: str,
        theme_id: str,
        environment: str,
        category: str | None = None,
        max_item_price_pkr: int | None = None,
    ) -> CatalogueSelection:
        """Return compatible catalogue rows without pretending to rank them."""

        event = _normalize_event(event_type)
        environment = environment.strip().lower().replace("-", "_")
        compatible: list[dict[str, str]] = []
        for row in self.items:
            events = {_normalize_event(value) for value in _tokens(row["event_types"])}
            themes = _tokens(row["theme_ids"])
            environments = _tokens(row["environments"])
            if event not in events and "all" not in events:
                continue
            if theme_id not in themes and "all" not in themes:
                continue
            if environment not in environments:
                continue
            if category and row["category"] != category:
                continue
            if max_item_price_pkr is not None and int(row["price_min_pkr"]) > max_item_price_pkr:
                continue
            compatible.append(row)

        compatible.sort(key=lambda row: (row["category"], int(row["price_min_pkr"]), row["item_id"]))
        return CatalogueSelection(
            items=tuple(compatible),
            total_price_min_pkr=sum(int(row["price_min_pkr"]) for row in compatible),
            total_price_max_pkr=sum(int(row["price_max_pkr"]) for row in compatible),
        )

    def evidence_for(self, item: dict[str, str]) -> dict[str, dict[str, str]]:
        """Expose the source, safety and photo evidence for one item."""

        return {
            "market_source": self.market_sources[item["market_source_id"]],
            "safety_profile": self.safety_profiles[item["safety_profile_id"]],
            "photo_candidate": self.photo_candidates[item["photo_candidate_id"]],
        }
