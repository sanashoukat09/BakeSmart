from app.schemas.professional import CalibrationValidationRequest
from app.services.calibration import CalibrationService


def _request(*, confirmed: bool, end_x: float = 0.5) -> CalibrationValidationRequest:
    return CalibrationValidationRequest.model_validate(
        {
            "image_width_px": 1000,
            "image_height_px": 500,
            "reference": {
                "photo_id": "venue-photo-0123456789abcdef0123",
                "label": "Measured table edge",
                "start": {"x_fraction": 0.1, "y_fraction": 0.5},
                "end": {"x_fraction": end_x, "y_fraction": 0.5},
                "known_length_m": 2.0,
                "plane": "table",
                "customer_confirmed": confirmed,
            },
        }
    )


def test_confirmed_reference_calculates_only_segment_scale():
    result = CalibrationService().validate_reference(_request(confirmed=True))

    assert result.status == "reference_recorded"
    assert result.segment_length_px == 400.0
    assert result.pixels_per_m_along_reference == 200.0
    assert result.metric_reference_ready is True
    assert result.global_projection_ready is False
    assert any("only along" in item for item in result.limitations)


def test_unconfirmed_reference_is_not_used_as_metric_scale():
    result = CalibrationService().validate_reference(_request(confirmed=False))

    assert result.status == "needs_customer_confirmation"
    assert result.pixels_per_m_along_reference is None
    assert result.metric_reference_ready is False
    assert result.global_projection_ready is False


def test_tiny_reference_segment_is_rejected():
    result = CalibrationService().validate_reference(
        _request(confirmed=True, end_x=0.11)
    )

    assert result.status == "invalid_reference"
    assert result.segment_length_px == 10.0
    assert result.pixels_per_m_along_reference is None
    assert result.metric_reference_ready is False
