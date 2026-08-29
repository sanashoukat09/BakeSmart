from pathlib import Path

import pytest

from training.local_only_policy import (
    assert_local_only_environment,
    assert_training_paths_allowed,
    audit_repository,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_repository_contains_no_hosted_ai_core_dependency_or_endpoint():
    assert audit_repository(PROJECT_DIR) == []


def test_hosted_provider_credentials_are_rejected():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        assert_local_only_environment({"GEMINI_API_KEY": "configured"})


def test_legacy_external_synthetic_images_are_rejected_from_new_training():
    with pytest.raises(ValueError, match="External synthetic material"):
        assert_training_paths_allowed(
            ["data/venue_vision/raw/gemini_synthetic_v1/images/gemini-venue-0001.png"]
        )


def test_reviewed_real_data_is_allowed():
    assert_training_paths_allowed(
        ["data/venue_vision/raw/real_v2/images/real-venue-0001.jpg"]
    )
