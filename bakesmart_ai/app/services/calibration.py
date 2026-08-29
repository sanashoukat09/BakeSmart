"""Local measurement and planar calibration for venue photos."""

from __future__ import annotations

from math import hypot, sqrt

import cv2
import numpy as np

from app.schemas.professional import (
    CalibrationValidationRequest,
    CalibrationValidationResponse,
    PlaneMetricPoint,
    PlanarCalibrationRequest,
    PlanarCalibrationResponse,
    PlanarProjectionRequest,
    PlanarProjectionResponse,
    ProjectedPlanePoint,
)

MIN_REFERENCE_PIXELS = 24.0
MIN_IMAGE_HULL_FRACTION = 0.0025
MIN_METRIC_HULL_AREA_M2 = 0.01
MAX_RMS_REPROJECTION_ERROR_PX = 10.0
MAX_REPROJECTION_ERROR_PX = 20.0


class CalibrationService:
    """Validate physical references and solve local planar homographies."""

    _reference_limitations = [
        "The pixels-per-metre value applies only along the marked reference segment.",
        "BakeSmart does not infer physical metres from visual appearance.",
        "A single line does not solve perspective, camera pose, or scene depth.",
        "Use the planar calibration endpoint with four or more confirmed correspondences for wall/floor/table projection.",
    ]

    _plane_limitations = [
        "The solved homography is valid only on the selected physical plane.",
        "Objects above, in front of, or behind that plane require 3D camera/scene geometry.",
        "This does not estimate camera intrinsics, full camera pose, or room depth.",
        "The current 3D viewer does not yet consume this planar projection automatically.",
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
                    *self._reference_limitations,
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
                    *self._reference_limitations,
                ],
            )

        pixels_per_m = segment_length_px / reference.known_length_m
        return CalibrationValidationResponse(
            status="reference_recorded",
            segment_length_px=round(segment_length_px, 6),
            pixels_per_m_along_reference=round(pixels_per_m, 6),
            metric_reference_ready=True,
            scale_source="customer_confirmed_reference",
            limitations=list(self._reference_limitations),
        )

    def calibrate_plane(
        self,
        request: PlanarCalibrationRequest,
    ) -> PlanarCalibrationResponse:
        response, _ = self._solve_plane(request)
        return response

    def project_plane_points(
        self,
        request: PlanarProjectionRequest,
    ) -> PlanarProjectionResponse:
        calibration, homography = self._solve_plane(request.calibration)
        if not calibration.planar_projection_ready or homography is None:
            return PlanarProjectionResponse(
                calibration=calibration,
                projected_points=[],
            )

        metric_points = np.asarray(
            [[point.x_m, point.y_m] for point in request.points_m],
            dtype=np.float64,
        )
        projected = cv2.perspectiveTransform(
            metric_points.reshape(-1, 1, 2),
            homography,
        ).reshape(-1, 2)
        width_denominator = max(request.calibration.image_width_px - 1, 1)
        height_denominator = max(request.calibration.image_height_px - 1, 1)
        output: list[ProjectedPlanePoint] = []
        for source, (x_px, y_px) in zip(request.points_m, projected, strict=True):
            x_fraction = float(x_px) / width_denominator
            y_fraction = float(y_px) / height_denominator
            output.append(
                ProjectedPlanePoint(
                    source=source,
                    x_px=round(float(x_px), 6),
                    y_px=round(float(y_px), 6),
                    x_fraction=round(x_fraction, 8),
                    y_fraction=round(y_fraction, 8),
                    inside_image=(
                        0 <= x_px <= width_denominator
                        and 0 <= y_px <= height_denominator
                    ),
                )
            )
        return PlanarProjectionResponse(
            calibration=calibration,
            projected_points=output,
        )

    def _solve_plane(
        self,
        request: PlanarCalibrationRequest,
    ) -> tuple[PlanarCalibrationResponse, np.ndarray | None]:
        confirmed_count = sum(anchor.customer_confirmed for anchor in request.anchors)
        if confirmed_count != len(request.anchors):
            return (
                PlanarCalibrationResponse(
                    status="needs_customer_confirmation",
                    plane_type=request.plane_type,
                    anchors_used=0,
                    confirmed_anchor_count=confirmed_count,
                    image_coverage_fraction=0.0,
                    fit_quality="unavailable",
                    planar_projection_ready=False,
                    limitations=[
                        "Every calibration anchor must be customer-confirmed before it can define physical scale.",
                        *self._plane_limitations,
                    ],
                ),
                None,
            )

        metric_points = np.asarray(
            [[anchor.plane.x_m, anchor.plane.y_m] for anchor in request.anchors],
            dtype=np.float64,
        )
        image_points = np.asarray(
            [
                [
                    anchor.image.x_fraction * (request.image_width_px - 1),
                    anchor.image.y_fraction * (request.image_height_px - 1),
                ]
                for anchor in request.anchors
            ],
            dtype=np.float64,
        )

        image_area = self._convex_hull_area(image_points)
        image_coverage_fraction = image_area / (
            request.image_width_px * request.image_height_px
        )
        metric_area = self._convex_hull_area(metric_points)
        unique_metric = len({tuple(point) for point in metric_points.tolist()})
        unique_image = len({tuple(point) for point in image_points.tolist()})

        if (
            unique_metric < 4
            or unique_image < 4
            or metric_area < MIN_METRIC_HULL_AREA_M2
            or image_coverage_fraction < MIN_IMAGE_HULL_FRACTION
        ):
            return (
                PlanarCalibrationResponse(
                    status="invalid_geometry",
                    plane_type=request.plane_type,
                    anchors_used=0,
                    confirmed_anchor_count=confirmed_count,
                    image_coverage_fraction=round(image_coverage_fraction, 8),
                    fit_quality="unavailable",
                    planar_projection_ready=False,
                    limitations=[
                        "Calibration anchors must contain at least four unique, non-collinear points spanning useful area in both metres and pixels.",
                        *self._plane_limitations,
                    ],
                ),
                None,
            )

        homography, _ = cv2.findHomography(metric_points, image_points, method=0)
        if homography is None or not np.isfinite(homography).all():
            return self._invalid_solver_response(
                request,
                confirmed_count,
                image_coverage_fraction,
                "OpenCV could not solve a stable plane homography from the supplied anchors.",
            )

        scale = homography[2, 2]
        if abs(scale) > 1e-12:
            homography = homography / scale
        determinant = float(np.linalg.det(homography))
        if abs(determinant) < 1e-12:
            return self._invalid_solver_response(
                request,
                confirmed_count,
                image_coverage_fraction,
                "The solved homography is singular; re-mark the plane using wider-spread anchors.",
            )

        projected = cv2.perspectiveTransform(
            metric_points.reshape(-1, 1, 2),
            homography,
        ).reshape(-1, 2)
        errors = np.linalg.norm(projected - image_points, axis=1)
        rms_error = sqrt(float(np.mean(np.square(errors))))
        max_error = float(np.max(errors))
        try:
            inverse = np.linalg.inv(homography)
        except np.linalg.LinAlgError:
            return self._invalid_solver_response(
                request,
                confirmed_count,
                image_coverage_fraction,
                "The solved homography could not be inverted; re-mark the calibration plane.",
            )
        inverse_scale = inverse[2, 2]
        if abs(inverse_scale) > 1e-12:
            inverse = inverse / inverse_scale

        poor_fit = (
            rms_error > MAX_RMS_REPROJECTION_ERROR_PX
            or max_error > MAX_REPROJECTION_ERROR_PX
        )
        fit_quality = self._fit_quality(
            anchor_count=len(request.anchors),
            rms_error=rms_error,
            max_error=max_error,
            image_coverage_fraction=image_coverage_fraction,
            poor_fit=poor_fit,
        )
        limitations = list(self._plane_limitations)
        if len(request.anchors) == 4:
            limitations.insert(
                0,
                "Exactly four anchors can fit a homography exactly; add one or more extra confirmed anchors for an independent residual check.",
            )
        if poor_fit:
            limitations.insert(
                0,
                "The marked correspondences disagree too much for safe planar projection; correct the measurements or clicked points.",
            )

        response = PlanarCalibrationResponse(
            status="poor_fit" if poor_fit else "calibrated",
            plane_type=request.plane_type,
            anchors_used=len(request.anchors),
            confirmed_anchor_count=confirmed_count,
            homography_m_to_px=self._matrix_payload(homography),
            homography_px_to_m=self._matrix_payload(inverse),
            rms_reprojection_error_px=round(rms_error, 6),
            max_reprojection_error_px=round(max_error, 6),
            image_coverage_fraction=round(image_coverage_fraction, 8),
            fit_quality=fit_quality,
            planar_projection_ready=not poor_fit,
            limitations=limitations,
        )
        return response, homography if not poor_fit else None

    def _invalid_solver_response(
        self,
        request: PlanarCalibrationRequest,
        confirmed_count: int,
        image_coverage_fraction: float,
        message: str,
    ) -> tuple[PlanarCalibrationResponse, None]:
        return (
            PlanarCalibrationResponse(
                status="invalid_geometry",
                plane_type=request.plane_type,
                anchors_used=0,
                confirmed_anchor_count=confirmed_count,
                image_coverage_fraction=round(image_coverage_fraction, 8),
                fit_quality="unavailable",
                planar_projection_ready=False,
                limitations=[message, *self._plane_limitations],
            ),
            None,
        )

    @staticmethod
    def _convex_hull_area(points: np.ndarray) -> float:
        hull = cv2.convexHull(points.astype(np.float32))
        return float(abs(cv2.contourArea(hull)))

    @staticmethod
    def _matrix_payload(matrix: np.ndarray) -> list[list[float]]:
        return [
            [round(float(value), 10) for value in row]
            for row in matrix.tolist()
        ]

    @staticmethod
    def _fit_quality(
        *,
        anchor_count: int,
        rms_error: float,
        max_error: float,
        image_coverage_fraction: float,
        poor_fit: bool,
    ) -> str:
        if poor_fit:
            return "low"
        if anchor_count >= 5 and rms_error <= 3 and max_error <= 6 and image_coverage_fraction >= 0.02:
            return "high"
        return "medium"


calibration_service = CalibrationService()
