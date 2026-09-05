from copy import deepcopy

from app.schemas.design import DesignRequest
from app.services.stage3_recommendation import Stage3RecommendationEngine


def _plans(payload: dict):
    request = DesignRequest.model_validate(payload)
    return Stage3RecommendationEngine().build_plans(
        request, request.event.theme_id
    )


def test_stage3_packages_are_varied_and_within_their_budget_shares(
    valid_design_request,
):
    plans = _plans(valid_design_request)

    identities = []
    counts = []
    for plan in plans.values():
        cost = sum(quantity * unit_cost for _, quantity, unit_cost in plan.selected)
        assert cost <= plan.budget_limit_pkr
        assert all(
            row["item_id"].startswith(
                ("backdrop-", "floor-", "lighting-", "table-", "sign-")
            )
            for row, _, _ in plan.selected
        )
        identities.append(tuple(row["item_id"] for row, _, _ in plan.selected))
        counts.append(len(plan.selected))

    assert len(set(identities)) == 3
    assert counts[0] < counts[1] < counts[2]


def test_stage3_respects_excluded_categories_and_colours(valid_design_request):
    payload = deepcopy(valid_design_request)
    payload["event"]["required_decor_categories"] = []
    payload["event"]["excluded_decor_categories"] = ["backdrop", "lighting"]
    payload["event"]["excluded_colors"] = ["black", "neon", "blush"]

    for plan in _plans(payload).values():
        for row, _, _ in plan.selected:
            assert row["category"] not in {"backdrop", "lighting"}
            assert "blush" not in row["color_tags"].split(";")


def test_stage3_rejects_components_that_do_not_fit_the_room(valid_design_request):
    payload = deepcopy(valid_design_request)
    payload["space"]["dimensions"] = {
        "width_m": 1.2,
        "depth_m": 1.2,
        "height_m": 1.5,
    }
    payload["event"]["required_decor_categories"] = []

    request = DesignRequest.model_validate(payload)
    for plan in Stage3RecommendationEngine().build_plans(
        request, request.event.theme_id
    ).values():
        for row, _, _ in plan.selected:
            assert int(row["width_cm"]) / 100 <= 1.2
            assert int(row["height_cm"]) / 100 <= 1.5


def test_stage3_is_deterministic(valid_design_request):
    first = _plans(valid_design_request)
    second = _plans(valid_design_request)
    assert first == second


def test_stage3_explanations_name_real_price_evidence(valid_design_request):
    plan = _plans(valid_design_request)["balanced"]
    assert plan.selected
    for row, _, _ in plan.selected:
        assert "Price range evidence:" in row["reason"]
        assert row["safety_notes"]


def test_stage3_prefers_approved_modules_for_a_flower_theme(valid_design_request):
    selected = {
        row["item_id"]
        for row, _, _ in _plans(valid_design_request)["balanced"].selected
    }

    assert {
        "backdrop-round-arch",
        "table-low-floral",
        "lighting-curtain",
    } <= selected


def test_stage3_uses_different_approved_assets_for_kids_and_glam_events(
    valid_design_request,
):
    kids = deepcopy(valid_design_request)
    kids["event"].update(
        {
            "event_type": "kids_birthday",
            "theme_id": "whimsical-kids",
            "preferred_colors": ["pink", "cream"],
            "excluded_colors": [],
        }
    )
    kids_ids = {
        row["item_id"] for row, _, _ in _plans(kids)["essential"].selected
    }

    glam = deepcopy(valid_design_request)
    glam["event"].update(
        {
            "event_type": "wedding",
            "theme_id": "glam-gold",
            "preferred_colors": ["gold", "blush"],
            "excluded_colors": [],
        }
    )
    glam["decoration_budget_pkr"] = 100_000
    glam_ids = {
        row["item_id"] for row, _, _ in _plans(glam)["statement"].selected
    }

    assert "backdrop-balloon-garland" in kids_ids
    assert {"backdrop-floral-arch", "lighting-uplight-set"} <= glam_ids
    assert kids_ids != glam_ids
