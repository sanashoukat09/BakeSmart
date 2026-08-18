# BakeSmart Venue Vision Bootstrap v1

This checkpoint was trained locally from random weights with BakeSmart's own
NumPy forward propagation, backpropagation and Adam implementation. It uses no
pretrained weights, external inference API or machine-learning framework.

The model labels 3×3 RGB pixel patches plus x/y position as `wall`, `floor`,
`door`, `window`, `furniture`, `outlet` or `walkway`. Training used 168
deterministic synthetic scenes, model selection used 36 validation scenes, and
the locked test pixels were rendered only after selection.

Locked synthetic-test results:

- Pixel accuracy: 0.9470
- Macro intersection-over-union: 0.7901
- Parameters: 2,791

These numbers are **not real-photo accuracy**. There are currently zero
expert-labelled real venue images. Runtime detections are therefore capped
below 0.50 confidence, labelled unconfirmed, and never converted into obstacle
coordinates or scale automatically. Customer measurements and obstacle-map
confirmation remain authoritative.
