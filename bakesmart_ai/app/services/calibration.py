"""Local measurement-reference validation for venue calibration."""

from math import hypot

from app.schemas.professional import (
    CalibrationValidationRequest,
    CalibrationValidationResponse,
)

MIN_REFERENCE_PIXELS = 24.0


class CalibrationService:
    """Validate a customer-measured line without pretending it solves the camera."""

    _limitations = [
        "The pixels-per-metre value applies only along the marked reference segment.",
        "BakeSmart does not infer physical metres from visual appearance.",
        "Camera intrinsics, pose, perspective/homography, and scene depth are not solved by this endpoint.",
        "Global photo projection remains unavailable until multi-point camera/plane calibration is implemented.",
    ]

    def validate_reference(
        self,
        request: CalibrationValidationRequest,
    ) -> CalibrationValidationResponse:
        reference = request.reference
        dx_px = (
            reference.end.x_fraction - reference.start.x_fraction
        ) * request.image_width_px
        dy_px = (
            reference.end.y_fraction - reference.start.y_fraction
        ) * request.image_height_px
        segment_length_px = hypot(dx_px, dy_px)
        scale_source = (
            "customer_confirmed_reference"
            if reference.customer_confirmed
            else "unverified_reference"
        )

        if segment_length_px < MIN_REFERENCE_PIXELS:
            return CalibrationValidationResponse(
                status="invalid_reference",
                segment_length_px=round(segment_length_px, 6),
                pixels_per_m_along_reference=None,
                metric_reference_ready=False,
                scale_source=scale_source,
                limitations=[
                    f"The marked reference must span at least {MIN_REFERENCE_PIXELS:.0f} pixels for stable validation.",
                    *self._limitations,
                ],
            )

        if not reference.customer_confirmed:
            return CalibrationValidationResponse(
                status="needs_customer_confirmation",
                segment_length_px=round(segment_length_px, 6),
                pixels_per_m_along_reference=None,
                metric_reference_ready=False,
                scale_source="unverified_reference",
                limitations=[
                    "Confirm the real measured length before BakeSmart uses this reference for metric calibration.",
                    *self._limitations,
                ],
            )

        pixels_per_m = segment_length_px / reference.known_length_m
        return CalibrationValidationResponse(
            status="reference_recorded",
            segment_length_px=round(segment_length_px, 6),
            pixels_per_m_along_reference=round(pixels_per_m, 6),
            metric_reference_ready=True,
            scale_source="customer_confirmed_reference",
            limitations=list(self._limitations),
        )


calibration_service = CalibrationService()
