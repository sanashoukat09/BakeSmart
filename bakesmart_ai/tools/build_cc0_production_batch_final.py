"""Final Batch-1 build entrypoint with mobile-budget floral topology.

This wraps the reviewed production builder and replaces only the marigold flower
primitive with a lower-topology version. The arrangement, physical envelope,
materials, provenance and validation gates remain unchanged.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from mathutils import Vector

# Blender does not guarantee that the directory containing a --python script is
# on sys.path. Add this tools directory explicitly before importing the reviewed
# base builder.
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_cc0_production_batch as base


def compact_marigold(name, center, orange, saffron, radius=0.031):
    """Create a visually dense marigold head using fewer mobile-friendly meshes."""
    c = Vector(center)
    base.ico(name + "_Core", c, (radius * 0.58, radius * 0.58, radius * 0.52), saffron)

    # Two overlapping low-poly rings. Earlier QA used 21 florets plus a core;
    # this uses 12 florets plus a core while keeping almost the same silhouette.
    for ring_index, (count, ring_radius, scale_factor) in enumerate(
        ((5, radius * 0.34, 0.48), (7, radius * 0.62, 0.52))
    ):
        for index in range(count):
            angle = 2 * math.pi * index / count + ring_index * 0.19
            z = 0.0035 * math.sin(index * 1.7 + ring_index)
            location = c + Vector(
                (math.cos(angle) * ring_radius, math.sin(angle) * ring_radius, z)
            )
            petal = base.ico(
                f"{name}_R{ring_index}_{index:02d}",
                location,
                (radius * scale_factor, radius * scale_factor * 0.88, radius * 0.36),
                orange if (index + ring_index) % 2 else saffron,
            )
            petal.rotation_euler[2] = angle


base.add_marigold = compact_marigold


if __name__ == "__main__":
    raise SystemExit(base.main())
