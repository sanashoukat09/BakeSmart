# BakeSmart Professional Calibration Foundation

BakeSmart must never infer physical metres from apparent object size in a customer photo. Metric scale comes from customer-confirmed measurements and customer-confirmed image points.

## Stage A: one-line measurement reference

`POST /api/v1/calibration/reference` validates a known physical length marked between two image points. The resulting pixels-per-metre value is valid only along that marked segment. It is not a perspective-correct room scale.

## Stage B: planar wall/floor/table calibration

`POST /api/v1/calibration/plane` accepts at least four confirmed correspondences. Each correspondence contains:

- an image point stored as normalized fractions;
- a measured 2D coordinate in metres on one physical wall, floor, or table plane;
- explicit customer confirmation.

The local OpenCV/NumPy solver computes a homography from plane metres to image pixels and its inverse. Point sets are rejected when they are duplicated, nearly collinear, cover too little image area, or cannot produce an invertible transform.

With more than four anchors, reprojection residuals provide a consistency check. Exactly four points can fit a homography exactly, so BakeSmart labels that fit as medium quality and asks for extra anchors when stronger validation is needed.

`POST /api/v1/calibration/plane/project` recomputes the confirmed planar solution and projects requested metre coordinates into the photo. Projection is limited to that physical plane.

## Truth boundary

Planar calibration does **not** yet mean BakeSmart knows the full camera or room. It does not estimate camera intrinsics, camera pose, ceiling/floor depth, or the 3D position of objects that sit away from the calibrated plane. The current WebGL planning viewer also does not yet consume this transform automatically.

The next professional stage is to combine calibrated wall/floor planes, confirmed room dimensions, and two-photo evidence into the metric room/constraint engine, then connect those transforms to photo projection and the renderer.
