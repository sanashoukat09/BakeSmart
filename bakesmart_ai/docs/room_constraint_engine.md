# BakeSmart Metric Room and Constraint Engine

This stage converts customer-confirmed room measurements into deterministic placement rules. It does not infer real-world metres from a photograph.

## Coordinate convention

BakeSmart uses metres.

- `x` runs across the measured focal wall.
- `y` runs from that wall into the room.
- `z` runs upward from the floor.
- Measured `ObstacleInput.position` is the minimum/lower corner of the obstacle box, matching the existing request validation contract.
- Rendered `ObjectPlacement.position.x_m` and `.y_m` are object-centre coordinates; `.z_m` is the object's base height.

The engine preserves these two existing conventions instead of silently reinterpreting stored measurements.

## Room assessment API

`POST /api/v1/constraints/room` accepts the measured `SpaceInput`, a minimum clearance of at least 0.9 m, and optional proposed scene objects.

The response includes:

- measured room bounds;
- protected obstacle/service zones;
- the largest usable focal span;
- a scale-aware backdrop/table/floor-decor planning target;
- available front circulation;
- hard constraint violations;
- whether the result is safe to use automatically or still needs manual review.

An unconfirmed obstacle map can never produce `hard_constraints_ready=true`.

## Focal span and scale targets

The engine does not use the whole wall blindly. Doors, windows, outlets and near-wall floor obstacles remove protected horizontal intervals. The largest remaining interval becomes the focal zone.

Visual scale is then based on that usable span. A large hall therefore receives a much wider planning backdrop target than a small living room. This directly avoids the earlier failure mode where a fixed small decoration occupied only a tiny fraction of a large venue.

The target is a **composition envelope**, not permission to stretch a real product. If the current procedural preview needs more visual width than one catalogue component provides, production must use a genuinely larger frame or multiple true-size modular pieces.

## Collision and circulation rules

The first professional constraint layer uses axis-aligned bounding boxes (AABBs).

It checks:

1. proposed objects remain inside measured room width, depth and height;
2. proposed objects do not enter protected measured-obstacle zones;
3. independent scene objects do not physically overlap;
4. the remaining front circulation is at least the requested minimum, which cannot be below 0.9 m.

The recommendation pipeline may apply scale-aware fitting only when the fitted candidate passes these hard checks. If it fails, the previous placement is retained and the response reports why the fitted candidate was rejected.

## Door limitation

The current request schema stores a door footprint but not hinge side or swing direction. BakeSmart therefore protects the measured door footprint and clearance conservatively but does **not** claim that a door-swing polygon has been solved.

A future schema should add hinge point, swing direction, opening angle and keep-clear polygon before automated door-swing verification is claimed.

## Current truth boundary

This stage does not yet provide:

- rotated-object OBB/SAT collision;
- detailed mesh-to-mesh collision;
- full camera pose or intrinsics;
- automatic projection of the 3D scene into the customer photo;
- real PBR modular production GLBs;
- cable routing, ceiling rigging or electrical-load verification.

Those remain later professional stages.

## Next stage

The next asset stage should replace the procedural composition envelope with true-size modular GLB assets and metadata. Asset selection/composition must satisfy the room engine's target span without stretching geometry, and every asset should carry real width/depth/height, anchor points, allowed placement zones, materials and collision bounds.
