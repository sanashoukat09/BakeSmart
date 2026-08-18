import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_design_request() -> dict:
    return {
        "customer_id": "customer-001",
        "space": {
            "area_type": "room",
            "venue_type": "living_room",
            "environment": "indoor",
            "dimensions": {
                "width_m": 3.0,
                "depth_m": 2.4,
                "height_m": 2.7,
            },
            "obstacles": [],
            "known_reference_m": 1.5,
            "photo_references": ["venue-photo-001"],
        },
        "event": {
            "event_type": "birthday",
            "guest_count": 35,
            "theme_id": "floral-romantic",
            "preferred_colors": ["blush-pink", "cream", "muted-gold"],
            "excluded_colors": ["black", "neon"],
            "required_decor_categories": ["backdrop", "cake-table"],
            "excluded_decor_categories": [],
        },
        "cake": {
            "cake_image_reference": "cake-photo-001",
            "shape": "round",
            "tiers": 2,
            "servings_required": 41,
            "diameter_m": 0.30,
            "height_m": 0.35,
        },
        "decoration_budget_pkr": 50000,
        "minimum_clearance_m": 0.9,
    }
