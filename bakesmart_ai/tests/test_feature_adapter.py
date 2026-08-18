from copy import deepcopy

import numpy as np

from app.schemas.design import DesignRequest
from app.services.feature_adapter import RequestFeatureAdapter


def test_request_adapter_uses_locked_42_feature_order(valid_design_request):
    adapter = RequestFeatureAdapter.load()
    request = DesignRequest.model_validate(valid_design_request)

    adapted = adapter.transform(request)

    assert adapted.matrix.shape == (1, 42)
    assert np.isfinite(adapted.matrix).all()
    assert adapted.derived_values["event_type"] == "birthday"
    assert adapted.derived_values["venue_type"] == "home"
    assert adapted.derived_values["preferred_color"] == "mixed"
    assert adapted.derived_values["preferred_style"] == "elegant"
    assert adapter.feature_columns[0] == "num__guest_count"
    assert adapter.feature_columns[-1] == "cat__preferred_style__unknown"


def test_request_adapter_is_deterministic(valid_design_request):
    adapter = RequestFeatureAdapter.load()
    request = DesignRequest.model_validate(valid_design_request)

    first = adapter.transform(request)
    second = adapter.transform(request)

    np.testing.assert_array_equal(first.matrix, second.matrix)
    assert first.warnings == second.warnings


def test_unknown_categories_use_frozen_unknown_buckets(valid_design_request):
    raw_request = deepcopy(valid_design_request)
    raw_request["event"]["event_type"] = "other"
    raw_request["space"]["venue_type"] = "other"
    raw_request["event"]["preferred_colors"] = ["transparent"]
    raw_request["event"]["theme_id"] = "not-in-catalog"
    request = DesignRequest.model_validate(raw_request)
    adapter = RequestFeatureAdapter.load()

    adapted = adapter.transform(request)
    values = dict(zip(adapter.feature_columns, adapted.matrix[0], strict=True))

    assert values["cat__event_type__unknown"] == 1
    assert values["cat__venue_type__unknown"] == 1
    assert values["cat__age_group__unknown"] == 1
    assert values["cat__preferred_color__unknown"] == 1
    assert values["cat__preferred_style__unknown"] == 1
